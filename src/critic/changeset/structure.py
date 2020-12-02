# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

import logging
import stat
from dataclasses import dataclass
from typing import AsyncIterable, Collection, Optional, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import gitaccess
from critic.api.transaction.protocol import CreatedAPIObject
from critic import pubsub
from critic.gitaccess import SHA1, GitTreeEntry, GitRepository


def _join_paths(dirname: Optional[str], basename: str) -> str:
    return f"{dirname}/{basename}" if dirname else basename


@dataclass
class ChangedEntry:
    path: str
    old_entry: Optional[GitTreeEntry]
    new_entry: Optional[GitTreeEntry]


async def _removed_tree(
    repository: GitRepository, path: Optional[str], sha1: SHA1
) -> AsyncIterable[ChangedEntry]:
    tree = (await repository.fetchone(sha1, wanted_object_type="tree")).asTree()
    for entry in tree.entries:
        async for changed_entry in _removed_entry(repository, path, entry):
            yield changed_entry


async def _removed_entry(
    repository: GitRepository, path: Optional[str], entry: GitTreeEntry
) -> AsyncIterable[ChangedEntry]:
    path = _join_paths(path, entry.name)
    if stat.S_ISDIR(entry.mode):
        async for changed_entry in _removed_tree(repository, path, entry.sha1):
            yield changed_entry
    else:
        yield ChangedEntry(path, entry, None)


async def _added_tree(
    repository: GitRepository, path: Optional[str], sha1: SHA1
) -> AsyncIterable[ChangedEntry]:
    tree = (await repository.fetchone(sha1, wanted_object_type="tree")).asTree()
    for entry in tree.entries:
        async for changed_entry in _added_entry(repository, path, entry):
            yield changed_entry


async def _added_entry(
    repository: GitRepository, path: Optional[str], entry: GitTreeEntry
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
    path: Optional[str] = None,
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
    include_paths: Optional[Collection[str]] = None,
) -> Collection[ChangedEntry]:
    if from_commit_sha1 is None:
        from_tree_sha1 = gitaccess.EMPTY_TREE_SHA1
    else:
        from_tree_sha1 = await repository.revparse(from_commit_sha1, object_type="tree")

    to_tree_sha1 = await repository.revparse(to_commit_sha1, object_type="tree")

    changed_entries = [
        changed_entry
        async for changed_entry in diff_trees(repository, from_tree_sha1, to_tree_sha1)
    ]

    if include_paths is not None:
        changed_entries = [
            changed_entry
            for changed_entry in changed_entries
            if changed_entry.path in include_paths
        ]

    return changed_entries


# def _create_merge(repository, merge_base, parent, merge_commit):
#     entries = compare_commits(repository, parent, merge_commit)
#     paths = set(entry.path for entry in entries)

#     reference_entries = compare_commits(repository, merge_commit, parent, paths)
#     reference_paths = set(entry.path for entry in reference_entries)

#     changed_entries = [changed_entry
#                        for changed_entry in changed_entries
#                        if changed_entry.path in reference_paths]


async def request(
    from_commit: api.commit.Commit,
    to_commit: api.commit.Commit,
    *,
    request_content: bool = False,
    request_highlight: bool = False,
    conflicts: bool = False,
) -> int:
    from . import content

    assert isinstance(to_commit, api.commit.Commit)

    if from_commit is not None:
        assert isinstance(from_commit, api.commit.Commit)
        assert from_commit.repository == to_commit.repository

    repository = to_commit.repository
    critic = repository.critic

    async with critic.transaction() as cursor:
        try:
            if from_commit is None:
                async with dbaccess.Query[int](
                    cursor,
                    """SELECT id
                         FROM changesets
                        WHERE repository={repository}
                          AND to_commit={to_commit}
                          AND from_commit IS NULL
                          AND for_merge IS NULL""",
                    repository=repository,
                    to_commit=to_commit,
                ) as result:
                    changeset_id = await result.scalar()
            else:
                async with dbaccess.Query[int](
                    cursor,
                    """SELECT id
                         FROM changesets
                        WHERE repository={repository}
                          AND to_commit={to_commit}
                          AND from_commit={from_commit}
                          AND for_merge IS NULL
                          AND is_replay={conflicts}""",
                    repository=repository,
                    to_commit=to_commit,
                    from_commit=from_commit,
                    conflicts=conflicts,
                ) as result:
                    changeset_id = await result.scalar()

            await cursor.execute(
                """DELETE
                     FROM changeseterrors
                    WHERE changeset={changeset_id}""",
                changeset_id=changeset_id,
            )
        except dbaccess.ZeroRowsInResult:
            async with dbaccess.Query[int](
                cursor,
                """INSERT
                     INTO changesets (repository, to_commit, from_commit, is_replay)
                   VALUES ({repository}, {to_commit}, {from_commit}, {conflicts})""",
                repository=repository,
                to_commit=to_commit,
                from_commit=from_commit,
                conflicts=conflicts,
                returning="id",
            ) as result:
                changeset_id = await result.scalar()

        if request_content:
            await content.request(
                critic,
                changeset_id,
                request_highlight=request_highlight,
                in_transaction=cursor,
            )

    await critic.wakeup_service("differenceengine")

    return changeset_id


async def request_merge(
    parent: api.commit.Commit, merge: api.commit.Commit
) -> Tuple[int, int]:
    from . import content

    assert isinstance(parent, api.commit.Commit)
    assert isinstance(merge, api.commit.Commit)
    assert merge.is_merge
    assert parent.isParentOf(merge)

    critic = merge.critic
    repository = merge.repository

    async with api.critic.Query[Tuple[int, int]](
        critic,
        """SELECT to_commit, id
             FROM changesets
            WHERE repository={repository}
              AND for_merge={merge}
              AND (from_commit={parent} OR to_commit={parent})""",
        repository=repository,
        parent=parent,
        merge=merge,
    ) as changesets_result:
        changeset_ids = dict(await changesets_result.all())

    if changeset_ids:
        changeset_id = changeset_ids[merge.id]
        reference_id = changeset_ids[parent.id]
    else:
        # Calculate merge base and insert the pair of changesets we want.
        mergebase = await repository.mergeBase(merge)

        async with critic.transaction() as cursor:
            # Primary changeset between merge parent and merge commit.
            async with dbaccess.Query[int](
                cursor,
                """INSERT
                     INTO changesets (
                            repository, to_commit, from_commit, for_merge
                          )
                   VALUES ({repository}, {merge}, {parent}, {merge})""",
                repository=repository,
                merge=merge,
                parent=parent,
                returning="id",
            ) as request_primary_result:
                changeset_id = await request_primary_result.scalar()

            await content.request(critic, changeset_id, in_transaction=cursor)

            # Reference changeset between merge base to merge parent.
            async with dbaccess.Query[int](
                cursor,
                """INSERT
                     INTO changesets (
                            repository, to_commit, from_commit, for_merge
                          )
                   VALUES ({repository}, {parent}, {mergebase}, {merge})""",
                repository=repository,
                parent=parent,
                merge=merge,
                mergebase=mergebase,
                returning="id",
            ) as request_reference_result:
                reference_id = await request_reference_result.scalar()

            await content.request(
                critic, reference_id, request_highlight=False, in_transaction=cursor
            )

            async with pubsub.connect("request_merge") as client:
                await client.publish(
                    cursor,
                    pubsub.PublishMessage(
                        pubsub.ChannelName("changesets"),
                        pubsub.Payload(CreatedAPIObject("changesets", changeset_id)),
                    ),
                )
                await client.publish(
                    cursor,
                    pubsub.PublishMessage(
                        pubsub.ChannelName("changesets"),
                        pubsub.Payload(CreatedAPIObject("changesets", reference_id)),
                    ),
                )

    return changeset_id, reference_id
