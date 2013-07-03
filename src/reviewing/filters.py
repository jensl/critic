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

import dbutils
import time
import re

class PatternError(Exception):
    def __init__(self, pattern, message):
        self.pattern = pattern
        self.message = message

    def __str__(self):
        return "%s: %s" % (self.pattern, self.message)

def sanitizePath(path):
    return re.sub("//+", "/", path.strip().lstrip("/")) or "/"

def validatePattern(pattern):
    if re.search(r"[^/]\*\*", pattern):
        raise PatternError(pattern, "** not at beginning of path or path component")
    elif re.search(r"\*\*$", pattern):
        raise PatternError(pattern, "** at end of path")
    elif re.search(r"\*\*[^/]", pattern):
        raise PatternError(pattern, "** not at end of path component")

def validPattern(pattern):
    try:
        validatePattern(pattern)
        return True
    except PatternError:
        return False

def compilePattern(pattern):
    wildcards = { "**/": "(?:[^/]+/)*",
                  "**": "(?:[^/]+(?:/|$))*",
                  "*": "[^/]*",
                  "?": "[^/]" }

    def escape(match):
        return "\\" + match.group(0)

    def replacement(match):
        return wildcards[match.group(0)]

    pattern = re.sub(r"[[{()+^$.\\|]", escape, pattern)

    return re.compile("^" + re.sub("\\*\\*(?:/|$)|\\*|\\?", replacement, pattern) + "$")

def hasWildcard(string):
    return "*" in string or "?" in string

class Path(object):
    def __init__(self, path):
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

    def __repr__(self):
        return "Path(%r)" % self.path

    def match(self, path):
        return bool(self.regexp.match(path))

    @staticmethod
    def cmp(pathA, pathB):
        # Filters that select individual files rank above filters that
        # select directories (even if the actual name of the file contains
        # wildcards.)
        if pathA.endswith("/") and not pathB.endswith("/"):
            return -1
        elif not pathA.endswith("/") and pathB.endswith("/"):
            return 1

        # Filters with more slashes in them rank higher than filters with fewer
        # slashes (but "**/" doesn't count as a slash, since it might match zero
        # slashes in practice.)
        specificityA = pathA.count("/") - len(re.findall(r"\*\*/", pathA))
        specificityB = pathB.count("/") - len(re.findall(r"\*\*/", pathB))
        if specificityA < specificityB:
            return -1
        elif specificityA > specificityB:
            return 1

        # Filters with fewer wildcards in them rank higher than filters with
        # more wildcards.
        wildcardsA = len(re.findall("\\*\\*|\\*|\\?", pathA))
        wildcardsB = len(re.findall("\\*\\*|\\*|\\?", pathB))
        if wildcardsA < wildcardsB:
            return 1
        elif wildcardsA > wildcardsB:
            return -1

        # Fall back to lexicographical ordering.  The filters probably won't
        # match the same files anyway, and if they do, well, at least this
        # way it's stable and predictable.
        return cmp(pathA, pathB)

class Filters:
    def __init__(self):
        # Pseudo-types:
        #   data: dict(user_id -> tuple(filter_type, delegate))
        #   file: tuple(file_id, data)
        #   tree: tuple(dict(dirname -> tree), dict(filename -> file))

        self.files = {}       # dict(path -> file)
        self.directories = {} # dict(dirname -> tree)
        self.root = ({}, {})  # tree
        self.data = {}        # dict(file_id -> data)

        # Note: The same per-file 'data' objects are referenced by all of
        # 'self.files', 'self.tree' and 'self.data'.

        self.directories[""] = self.root

    def setFiles(self, db, file_ids=None, review=None):
        assert (file_ids is None) != (review is None)

        cursor = db.cursor()

        if file_ids is None:
            cursor.execute("SELECT DISTINCT file FROM reviewfiles WHERE review=%s", (review.id,))
            file_ids = [file_id for (file_id,) in cursor]

        cursor.execute("SELECT id, path FROM files WHERE id=ANY (%s)", (file_ids,))

        for file_id, path in cursor:
            data = {}

            self.files[path] = (file_id, data)
            self.data[file_id] = data

            if "/" in path:
                dirname, filename = path.rsplit("/", 1)

                def find_tree(dirname):
                    tree = self.directories.get(dirname)
                    if tree:
                        return tree
                    tree = self.directories[dirname] = ({}, {})
                    if "/" in dirname:
                        dirname, basename = dirname.rsplit("/", 1)
                        find_tree(dirname)[0][basename] = tree
                    else:
                        self.root[0][dirname] = tree
                    return tree

                tree = find_tree(dirname)
            else:
                filename = path
                tree = self.root

            tree[1][filename] = self.files[path]

    def addFilter(self, user_id, path, filter_type, delegate):
        def files_in_tree(components, tree):
            for dirname, child_tree in tree[0].items():
                for f in files_in_tree(components + [dirname], child_tree):
                    yield f
            dirname = "/".join(components) + "/" if components else ""
            for filename, (_, data) in tree[1].items():
                yield dirname, filename, data

        if not path:
            dirname, filename = "", None
            components = []
        elif "/" in path:
            dirname, filename = path.rsplit("/", 1)
            if not dirname:
                dirname = ""
                components = []
            else:
                components = dirname.split("/")
            if not filename:
                filename = None
        else:
            dirname, filename = "", path
            components = []

        def hasWildcard(string):
            return "*" in string or "?" in string

        if hasWildcard(path):
            tree = self.root
            files = []

            for index, component in enumerate(components):
                if hasWildcard(component):
                    wild_dirname = "/".join(components[index:]) + "/"
                    break
                else:
                    tree = tree[0].get(component)
                    if not tree:
                        return
            else:
                wild_dirname = None

            re_filename = compilePattern(filename or "*")

            if wild_dirname:
                re_dirname = compilePattern(wild_dirname)

                for dirname, filename, data in files_in_tree([], tree):
                    if re_dirname.match(dirname) and re_filename.match(filename):
                        files.append(data)
            else:
                for filename, (_, data) in tree[1].items():
                    if re_filename.match(filename):
                        files.append(data)
        else:
            if filename:
                if path in self.files:
                    files = [self.files[path][1]]
                else:
                    return
            else:
                if dirname in self.directories:
                    files = [data for _, _, data in files_in_tree([dirname], self.directories[dirname])]
                else:
                    return

        for data in files:
            if filter_type == "ignored":
                if user_id in data:
                    del data[user_id]
            else:
                data[user_id] = (filter_type, delegate)

    def addFilters(self, filters):
        def compareFilters(filterA, filterB):
            return Path.cmp(filterA[1], filterB[1])

        sorted_filters = sorted(filters, cmp=compareFilters)

        for user_id, path, filter_type, delegate in sorted_filters:
            self.addFilter(user_id, path, filter_type, delegate)

    class Review:
        def __init__(self, review_id, applyfilters, applyparentfilters, repository):
            self.id = review_id
            self.applyfilters = applyfilters
            self.applyparentfilters = applyparentfilters
            self.repository = repository

    def load(self, db, repository=None, review=None, recursive=False, user=None,
             added_review_filters=[], removed_review_filters=[]):
        assert (repository is None) != (review is None)

        cursor = db.cursor()

        if user is not None: user_filter = " AND uid=%d" % user.id
        else: user_filter = ""

        def loadGlobal(repository, recursive):
            if recursive and repository.parent:
                loadGlobal(repository.parent, recursive)

            cursor.execute("""SELECT filters.uid, filters.path, filters.type, filters.delegate
                                FROM filters
                                JOIN users ON (users.id=filters.uid)
                               WHERE filters.repository=%%s
                                 AND users.status!='retired'
                                     %s""" % user_filter,
                           (repository.id,))
            self.addFilters(cursor)

        def loadReview(review):
            cursor.execute("""SELECT reviewfilters.uid, reviewfilters.path, reviewfilters.type, NULL
                                FROM reviewfilters
                                JOIN users ON (users.id=reviewfilters.uid)
                               WHERE reviewfilters.review=%%s
                                 AND users.status!='retired'
                                     %s""" % user_filter,
                           (review.id,))
            if added_review_filters or removed_review_filters:
                review_filters = set(cursor.fetchall())
                review_filters -= set(map(tuple, removed_review_filters))
                review_filters |= set(map(tuple, added_review_filters))
                self.addFilters(list(review_filters))
            else:
                self.addFilters(cursor)

        if review:
            if review.applyfilters:
                loadGlobal(review.repository, review.applyparentfilters)
            loadReview(review)
        else:
            loadGlobal(repository, recursive)

    def getUserFileAssociation(self, user_id, file_id):
        user_id = int(user_id)
        file_id = int(file_id)

        data = self.data.get(file_id)
        if not data:
            return None

        data = data.get(user_id)
        if not data:
            return None

        return data[0]

    def isReviewer(self, user_id, file_id):
        return self.getUserFileAssociation(user_id, file_id) == 'reviewer'

    def isWatcher(self, user_id, file_id):
        return self.getUserFileAssociation(user_id, file_id) == 'watcher'

    def isRelevant(self, user_id, file_id):
        return self.getUserFileAssociation(user_id, file_id) in ('reviewer', 'watcher')

    def listUsers(self, file_id):
        return self.data.get(file_id, {})

    def getRelevantFiles(self):
        relevant = {}

        for file_id, data in self.data.items():
            for user_id, (filter_type, _) in data.items():
                if filter_type in ('reviewer', 'watcher'):
                    relevant.setdefault(user_id, set()).add(file_id)

        return relevant

def getMatchedFiles(repository, paths):
    paths = [Path(path) for path in sorted(paths, cmp=Path.cmp, reverse=True)]

    common_fixedDirname = None
    for path in paths:
        if path.fixedDirname is None:
            common_fixedDirname = []
            break
        elif common_fixedDirname is None:
            common_fixedDirname = path.fixedDirname.split("/")
        else:
            for index, component in enumerate(path.fixedDirname.split("/")):
                if index == len(common_fixedDirname):
                    break
                elif common_fixedDirname[index] != component:
                    del common_fixedDirname[index:]
                    break
            else:
                del common_fixedDirname[index:]
    common_fixedDirname = "/".join(common_fixedDirname)

    args = ["ls-tree", "-r", "--name-only", "HEAD"]

    if common_fixedDirname:
        args.append(common_fixedDirname + "/")

    matched = dict((path.path, []) for path in paths)

    if repository.isEmpty():
        return matched

    filenames = repository.run(*args).splitlines()

    if len(paths) == 1 and not paths[0].wildDirname and not paths[0].filename:
        return { paths[0].path: filenames }

    for filename in filenames:
        for path in paths:
            if path.match(filename):
                matched[path.path].append(filename)
                break

    return matched

def countMatchedFiles(repository, paths):
    matched = getMatchedFiles(repository, paths)
    return dict((path, len(filenames)) for path, filenames in matched.items())
