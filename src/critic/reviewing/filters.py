# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import (
    Any,
    Collection,
    Dict,
    Generator,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from critic import api
from critic.api import repositoryfilter
from critic.api.repositoryfilter import RepositoryFilter


class PatternError(Exception):
    def __init__(self, pattern: str, message: str):
        self.pattern = pattern
        self.message = message

    def __str__(self) -> str:
        return f"{self.pattern}: {self.message}"


def sanitizePath(path: str) -> str:
    return re.sub("//+", "/", path.strip().lstrip("/")) or "/"


def validatePattern(pattern: str) -> None:
    if re.search(r"[^/]\*\*", pattern):
        raise PatternError(pattern, "** not at beginning of path or path component")
    elif re.search(r"\*\*$", pattern):
        raise PatternError(pattern, "** at end of path")
    elif re.search(r"\*\*[^/]", pattern):
        raise PatternError(pattern, "** not at end of path component")


def validPattern(pattern: str) -> bool:
    try:
        validatePattern(pattern)
        return True
    except PatternError:
        return False


def compilePattern(pattern: str) -> re.Pattern[str]:
    wildcards = {
        "**/": "(?:[^/]+/)*",
        "**": "(?:[^/]+(?:/|$))*",
        "*": "[^/]*",
        "?": "[^/]",
    }

    def escape(match: re.Match[str]) -> str:
        return "\\" + match.group(0)

    def replacement(match: re.Match[str]) -> str:
        return wildcards[match.group(0)]

    pattern = re.sub(r"[[{()+^$.\\|]", escape, pattern)

    return re.compile("^" + re.sub("\\*\\*(?:/|$)|\\*|\\?", replacement, pattern) + "$")


def hasWildcard(string: str) -> bool:
    return "*" in string or "?" in string


class Path(object):
    fixedDirname: str
    wildDirname: Optional[str]
    filenameRegExp: Optional[re.Pattern[str]]

    def __init__(self, path: str):
        path = path.lstrip("/")

        self.path = path

        if hasWildcard(path):
            validatePattern(path)

        if path.endswith("/"):
            self.regexp = compilePattern(path + "**/*")
        else:
            self.regexp = compilePattern(path)

        if not path:
            self.dirname, self.filename = "", None
        elif "/" in path:
            self.dirname, self.filename = path.rsplit("/", 1)
            if not self.filename:
                self.filename = None
        else:
            self.dirname, self.filename = "", path

        if hasWildcard(self.dirname):
            components = self.dirname.split("/")
            for index, component in enumerate(components):
                if hasWildcard(component):
                    self.fixedDirname = "/".join(components[:index])
                    self.wildDirname = "/".join(components[index:])
                    self.wildDirnameRegExp = compilePattern(self.wildDirname)
                    break
        else:
            self.fixedDirname = self.dirname
            self.wildDirname = None

        if self.filename and hasWildcard(self.filename):
            self.filenameRegExp = compilePattern(self.filename)
        else:
            self.filenameRegExp = None

    def __repr__(self) -> str:
        return "Path(%r)" % self.path

    def match(self, path: str) -> bool:
        return bool(self.regexp.match(path))

    @staticmethod
    def lt(pathA, pathB) -> bool:
        # Filters that select individual files rank above filters that
        # select directories (even if the actual name of the file contains
        # wildcards.)
        if pathA.endswith("/") and not pathB.endswith("/"):
            return True
        elif not pathA.endswith("/") and pathB.endswith("/"):
            return False

        # Filters with more slashes in them rank higher than filters with fewer
        # slashes (but "**/" doesn't count as a slash, since it might match zero
        # slashes in practice.)
        specificityA = pathA.count("/") - len(re.findall(r"\*\*/", pathA))
        specificityB = pathB.count("/") - len(re.findall(r"\*\*/", pathB))
        if specificityA < specificityB:
            return True
        elif specificityA > specificityB:
            return False

        # Filters with fewer wildcards in them rank higher than filters with
        # more wildcards.
        wildcardsA = len(re.findall("\\*\\*|\\*|\\?", pathA))
        wildcardsB = len(re.findall("\\*\\*|\\*|\\?", pathB))
        if wildcardsA < wildcardsB:
            return False
        elif wildcardsA > wildcardsB:
            return True

        # Fall back to lexicographical ordering.  The filters probably won't
        # match the same files anyway, and if they do, well, at least this
        # way it's stable and predictable.
        return pathA < pathB


Filter = Union[api.repositoryfilter.RepositoryFilter, api.reviewfilter.ReviewFilter]


class FilterSet(Set[Filter]):
    filter_type: Optional[api.repositoryfilter.FilterType]

    def __init__(self):
        self.filter_type = None

    def add(self, filter: Filter) -> None:
        if self.filter_type and filter.type != self.filter_type:
            self.clear()
        super().add(filter)

    @property
    async def scopes(self) -> Collection[api.reviewscope.ReviewScope]:
        if self.filter_type != "reviewer":
            return ()
        scopes: Set[api.reviewscope.ReviewScope] = set()
        for filter in self:
            scopes.update(await filter.scopes)
        return scopes


FileData = Dict[api.user.User, FilterSet]


@dataclass
class FileInfo:
    file: api.file.File
    data: FileData


@dataclass
class Tree:
    subtrees: Dict[str, Tree]
    files: Dict[str, FileInfo]


class Filters:
    files: Dict[str, FileInfo]
    directories: Dict[str, Tree]
    data: Dict[api.file.File, FileData]
    matching_filters: Dict[api.user.User, Set[Filter]]
    active_filters: Dict[api.user.User, Set[Filter]]
    matched_files: Dict[Filter, Set[api.file.File]]

    def __init__(self) -> None:
        # Pseudo-types:
        #   data: dict(user_id -> tuple(filter_type, delegate))
        #   file: tuple(file_id, data)
        #   tree: tuple(dict(dirname -> tree), dict(filename -> file))

        self.files = {}  # dict(path -> file)
        self.directories = {}  # dict(dirname -> tree)
        self.root = Tree({}, {})  # tree
        self.data = {}  # dict(file_id -> data)
        self.matching_filters = {}  # dict(user_id -> set(Filter))
        self.active_filters = {}  # dict(user_id -> set(Filter))
        self.matched_files = {}  # dict(Filter -> set(file_id))

        # Note: The same per-file 'data' objects are referenced by all of
        # 'self.files', 'self.tree' and 'self.data'.

        self.directories[""] = self.root

    def setFiles(self, files: Collection[api.file.File]) -> None:
        for file in files:
            data: FileData = {}

            self.files[file.path] = FileInfo(file, data)
            self.data[file] = data

            if "/" in file.path:
                dirname, filename = file.path.rsplit("/", 1)

                def find_tree(dirname: str) -> Tree:
                    tree = self.directories.get(dirname)
                    if tree:
                        return tree
                    tree = self.directories[dirname] = Tree({}, {})
                    if "/" in dirname:
                        dirname, basename = dirname.rsplit("/", 1)
                        find_tree(dirname).subtrees[basename] = tree
                    else:
                        self.root.subtrees[dirname] = tree
                    return tree

                tree = find_tree(dirname)
            else:
                filename = file.path
                tree = self.root

            tree.files[filename] = self.files[file.path]

    async def addFilter(self, filter: Filter) -> None:
        def files_in_tree(
            components: List[str], tree: Tree
        ) -> Iterable[Tuple[str, str, FileInfo]]:
            for dirname, child_tree in tree.subtrees.items():
                for f in files_in_tree(components + [dirname], child_tree):
                    yield f
            dirname = "/".join(components) + "/" if components else ""
            for filename, file_info in tree.files.items():
                yield dirname, filename, file_info

        components: List[str]

        if not filter.path:
            dirname, filename = "", None
            components = []
        elif "/" in filter.path:
            dirname, filename = filter.path.rsplit("/", 1)
            if not dirname:
                dirname = ""
                components = []
            else:
                components = dirname.split("/")
            if not filename:
                filename = None
        else:
            dirname, filename = "", filter.path
            components = []

        def hasWildcard(string):
            return "*" in string or "?" in string

        matched_files: Set[api.file.File] = set()
        files = []

        if hasWildcard(filter.path):
            tree: Optional[Tree] = self.root

            wild_dirname: Optional[str]

            for index, component in enumerate(components):
                assert tree
                if hasWildcard(component):
                    wild_dirname = "/".join(components[index:]) + "/"
                    break
                else:
                    tree = tree.subtrees.get(component)
                    if not tree:
                        return
            else:
                wild_dirname = None

            assert tree

            re_filename = compilePattern(filename or "*")

            if wild_dirname:
                re_dirname = compilePattern(wild_dirname)

                for dirname, filename, file_info in files_in_tree([], tree):
                    if re_dirname.match(dirname) and re_filename.match(filename):
                        matched_files.add(file_info.file)
                        files.append(file_info.data)
            else:
                for filename, file_info in tree.files.items():
                    if re_filename.match(filename):
                        matched_files.add(file_info.file)
                        files.append(file_info.data)
        else:
            if filename:
                if filter.path in self.files:
                    file_info = self.files[filter.path]
                    matched_files.add(file_info.file)
                    files.append(file_info.data)
                else:
                    return
            else:
                if dirname in self.directories:
                    for _, _, file_info in files_in_tree(
                        [dirname], self.directories[dirname]
                    ):
                        matched_files.add(file_info.file)
                        files.append(file_info.data)
                else:
                    return

        self.matched_files[filter] = matched_files

        if not files:
            return

        subject = await filter.subject

        self.matching_filters.setdefault(subject, set()).add(filter)

        if filter.type == "ignored":
            for data in files:
                if subject in data:
                    del data[subject]
        elif filter.type in ("reviewer", "watcher"):
            self.active_filters.setdefault(subject, set()).add(filter)
            for data in files:
                data.setdefault(subject, FilterSet()).add(filter)

    async def addFilters(self, filters: Collection[Filter]) -> None:
        class OrderedFilter:
            def __init__(self, filter: Filter):
                self.filter = filter
                self.type = (
                    0
                    if isinstance(filter, api.repositoryfilter.RepositoryFilter)
                    else 1
                )
                self.path = filter.path

            def __lt__(self, other: object) -> bool:
                assert isinstance(other, OrderedFilter)
                if self.type < other.type:
                    return True
                elif self.type == other.type:
                    return Path.lt(self.path, other.path)
                return False

            def __eq__(self, other: object) -> bool:
                assert isinstance(other, OrderedFilter)
                return self.filter == other.filter

        for ordered_filter in sorted(map(OrderedFilter, filters)):
            await self.addFilter(ordered_filter.filter)

    def getUserFileAssociation(
        self, user: api.user.User, file: api.file.File
    ) -> Optional[api.repositoryfilter.FilterType]:
        file_data = self.data.get(file)
        if not file_data:
            return None

        filters = file_data.get(user)
        if not filters:
            return None

        return next(iter(filters)).type

    def isReviewer(self, user: api.user.User, file: api.file.File) -> bool:
        return self.getUserFileAssociation(user, file) == "reviewer"

    def isWatcher(self, user: api.user.User, file: api.file.File) -> bool:
        return self.getUserFileAssociation(user, file) == "watcher"

    def isRelevant(self, user: api.user.User, file: api.file.File) -> bool:
        return self.getUserFileAssociation(user, file) in ("reviewer", "watcher")

    def listUsers(self, file: api.file.File) -> Dict[api.user.User, FilterSet]:
        return self.data.get(file, {})

    def getRelevantFiles(self) -> Mapping[api.user.User, Collection[api.file.File]]:
        relevant: Dict[api.user.User, Set[api.file.File]] = {}

        for file, data in self.data.items():
            for user in data.keys():
                relevant.setdefault(user, set()).add(file)

        return relevant

    def getActiveFilters(self, user: api.user.User) -> Collection[Filter]:
        return self.active_filters.get(user, set())


# def getMatchedFiles(repository: api.repository.Repository, paths: Iterable[str]):
#     paths = [Path(path) for path in sorted(paths, cmp=Path.cmp, reverse=True)]

#     common_fixedDirname = None
#     for path in paths:
#         if path.fixedDirname is None:
#             common_fixedDirname = []
#             break
#         elif common_fixedDirname is None:
#             common_fixedDirname = path.fixedDirname.split("/")
#         else:
#             for index, component in enumerate(path.fixedDirname.split("/")):
#                 if index == len(common_fixedDirname):
#                     break
#                 elif common_fixedDirname[index] != component:
#                     del common_fixedDirname[index:]
#                     break
#             else:
#                 del common_fixedDirname[index:]
#     common_fixedDirname = "/".join(common_fixedDirname)

#     args = ["ls-tree", "-r", "--name-only", "HEAD"]

#     if common_fixedDirname:
#         args.append(common_fixedDirname + "/")

#     matched = dict((path.path, []) for path in paths)

#     if repository.isEmpty():
#         return matched

#     filenames = repository.run(*args).splitlines()

#     if len(paths) == 1 and not paths[0].wildDirname and not paths[0].filename:
#         return {paths[0].path: filenames}

#     for filename in filenames:
#         for path in paths:
#             if path.match(filename):
#                 matched[path.path].append(filename)
#                 break

#     return matched


# def countMatchedFiles(repository, paths):
#     matched = getMatchedFiles(repository, paths)
#     return dict((path, len(filenames)) for path, filenames in matched.items())
