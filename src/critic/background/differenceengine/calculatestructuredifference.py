# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

from dataclasses import dataclass
import logging
import stat
from typing import AsyncIterable, Collection, Iterable, Optional

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import gitaccess
from critic.gitaccess import SHA1, GitRepository, GitTreeEntry

from .changedfile import ChangedFile
from .examinefiles import ExamineFiles
from .job import Job, GroupType


def _join_paths(dirname: Optional[bytes], basename: bytes) -> bytes:
    return dirname + b"/" + basename if dirname else basename


@dataclass
class ChangedEntry:
    path: bytes
    old_entry: Optional[GitTreeEntry]
    new_entry: Optional[GitTreeEntry]


async def _removed_tree(
    repository: GitRepository, path: Optional[bytes], sha1: SHA1
) -> AsyncIterable[ChangedEntry]:
    tree = (await repository.fetchone(sha1, wanted_object_type="tree")).asTree()
    for entry in tree.entries:
        async for changed_entry in _removed_entry(repository, path, entry):
            yield changed_entry


async def _removed_entry(
    repository: GitRepository, path: Optional[bytes], entry: GitTreeEntry
) -> AsyncIterable[ChangedEntry]:
    path = _join_paths(path, entry.name)
    if stat.S_ISDIR(entry.mode):
        async for changed_entry in _removed_tree(repository, path, entry.sha1):
            yield changed_entry
    else:
        yield ChangedEntry(path, entry, None)


async def _added_tree(
    repository: GitRepository, path: Optional[bytes], sha1: SHA1
) -> AsyncIterable[ChangedEntry]:
    tree = (await repository.fetchone(sha1, wanted_object_type="tree")).asTree()
    for entry in tree.entries:
        async for changed_entry in _added_entry(repository, path, entry):
            yield changed_entry


async def _added_entry(
    repository: GitRepository, path: Optional[bytes], entry: GitTreeEntry
) -> AsyncIterable[ChangedEntry]:
    path = _join_paths(path, entry.name)
    if stat.S_ISDIR(entry.mode):
        async for changed_entry in _added_tree(repository, path, entry.sha1):
            yield changed_entry
    else:
        yield ChangedEntry(path, None, entry)


async def diff_trees(
    repository: GitRepository,
    old_tree_sha1: SHA1,
    new_tree_sha1: SHA1,
    path: Optional[bytes] = None,
) -> AsyncIterable[ChangedEntry]:
    """Compare two trees and return a list of differing entries

    The return value is a list of ChangedEntry objects."""

    old_tree = (
        await repository.fetchone(old_tree_sha1, wanted_object_type="tree")
    ).asTree()
    new_tree = (
        await repository.fetchone(new_tree_sha1, wanted_object_type="tree")
    ).asTree()

    old_names = set(old_tree.by_name.keys())
    new_names = set(new_tree.by_name.keys())

    common_names = old_names & new_names
    removed_names = old_names - common_names
    added_names = new_names - common_names

    for name in removed_names:
        async for changed_entry in _removed_entry(
            repository, path, old_tree.by_name[name]
        ):
            yield changed_entry
    for name in added_names:
        async for changed_entry in _added_entry(
            repository, path, new_tree.by_name[name]
        ):
            yield changed_entry

    for name in common_names:
        old_entry = old_tree.by_name[name]
        old_sha1 = old_entry.sha1
        old_mode = old_entry.mode

        new_entry = new_tree.by_name[name]
        new_sha1 = new_entry.sha1
        new_mode = new_entry.mode

        if old_sha1 != new_sha1 or old_mode != new_mode:
            changed_path = _join_paths(path, name)

            common_mode = old_mode & new_mode
            removed_mode = old_mode - common_mode
            added_mode = new_mode - common_mode

            if stat.S_ISDIR(common_mode):
                assert old_sha1 != new_sha1
                async for changed_entry in diff_trees(
                    repository, old_sha1, new_sha1, changed_path
                ):
                    yield changed_entry
            elif stat.S_ISDIR(removed_mode):
                # Directory replaced by non-directory.
                async for changed_entry in _removed_tree(
                    repository, changed_path, old_sha1
                ):
                    yield changed_entry
                yield ChangedEntry(changed_path, None, new_entry)
            elif stat.S_ISDIR(added_mode):
                # Non-directory replaced by directory.
                yield ChangedEntry(changed_path, old_entry, None)
                async for changed_entry in _added_tree(
                    repository, changed_path, new_sha1
                ):
                    yield changed_entry
            else:
                yield ChangedEntry(changed_path, old_entry, new_entry)


async def compare_commits(
    repository: GitRepository,
    from_commit_sha1: SHA1,
    to_commit_sha1: SHA1,
) -> Collection[ChangedEntry]:
    if from_commit_sha1 is None:
        from_tree_sha1 = gitaccess.EMPTY_TREE_SHA1
    else:
        from_tree_sha1 = await repository.revparse(from_commit_sha1, object_type="tree")

    to_tree_sha1 = await repository.revparse(to_commit_sha1, object_type="tree")

    return [
        changed_entry
        async for changed_entry in diff_trees(repository, from_tree_sha1, to_tree_sha1)
    ]


class CalculateStructureDifference(Job):
    """Calculate the structure difference"""

    def __init__(
        self,
        group: GroupType,
        changeset_id: int,
        from_commit_sha1: SHA1,
        to_commit_sha1: SHA1,
        content_difference_requested: bool,
        for_merge: bool,
    ):
        super().__init__(group, ())
        self.changeset_id = changeset_id
        self.from_commit_sha1 = from_commit_sha1
        self.to_commit_sha1 = to_commit_sha1
        self.content_difference_requested = content_difference_requested
        self.for_merge = for_merge

    async def execute(self) -> None:
        async with self.group.repository() as gitrepository:
            changed_entries = await compare_commits(
                gitrepository,
                self.from_commit_sha1,
                self.to_commit_sha1,
            )

        def sha1(entry: Optional[GitTreeEntry]) -> Optional[SHA1]:
            return None if entry is None else entry.sha1

        def mode(entry: Optional[GitTreeEntry]) -> Optional[int]:
            return None if entry is None else entry.mode

        decode = self.group.as_changeset.decode_new

        self.changed_files = [
            ChangedFile(
                None,
                decode.path(changed_entry.path),
                sha1(changed_entry.old_entry),
                mode(changed_entry.old_entry),
                sha1(changed_entry.new_entry),
                mode(changed_entry.new_entry),
            )
            for changed_entry in changed_entries
        ]

    def referenced_paths(self) -> Collection[str]:
        return set(changed_file.path for changed_file in self.changed_files)

    async def update_database(self, critic: api.critic.Critic) -> None:
        file_ids = self.group.runner.file_ids

        for changed_file in self.changed_files:
            changed_file.file_id = file_ids[changed_file.path]

        async with critic.transaction() as cursor:
            # Faster query, for file ids we have cached.
            await cursor.executemany(
                """INSERT
                     INTO changesetfiles (
                            changeset, file, old_sha1, old_mode, new_sha1, new_mode
                          ) VALUES (
                            {changeset_id}, {file_id}, {old_sha1}, {old_mode},
                            {new_sha1}, {new_mode}
                          )""",
                (
                    dbaccess.parameters(
                        changeset_id=self.changeset_id,
                        file_id=changed_file.file_id,
                        old_sha1=changed_file.old_sha1,
                        old_mode=changed_file.old_mode,
                        new_sha1=changed_file.new_sha1,
                        new_mode=changed_file.new_mode,
                    )
                    for changed_file in self.changed_files
                ),
            )

            await cursor.execute(
                """UPDATE changesets
                      SET processed=TRUE,
                          complete={complete}
                    WHERE id={changeset_id}""",
                changeset_id=self.changeset_id,
                complete=not self.for_merge,
            )

    def follow_ups(self) -> Iterable[ExamineFiles]:
        if self.content_difference_requested:
            yield from ExamineFiles.for_files(
                self.group,
                self.from_commit_sha1,
                self.to_commit_sha1,
                self.changed_files,
            )
