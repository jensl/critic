# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2020 the Critic contributors, Opera Software ASA
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

from typing import Collection, NamedTuple, Optional, Tuple

from critic import api
from critic import dbaccess
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject


class FindChangesetId:
    def __init__(
        self,
        from_commit: Optional[api.commit.Commit],
        to_commit: api.commit.Commit,
        conflicts: bool,
    ):
        self.from_commit = from_commit
        self.to_commit = to_commit
        self.conflicts = conflicts

    @property
    def table_names(self) -> Collection[str]:
        return ()

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> Optional[int]:
        if self.from_commit is None:
            async with dbaccess.Query[int](
                cursor,
                """SELECT id
                     FROM changesets
                    WHERE repository={repository}
                      AND to_commit={to_commit}
                      AND from_commit IS NULL
                      AND for_merge IS NULL""",
                repository=self.to_commit.repository,
                to_commit=self.to_commit,
            ) as result:
                return await result.maybe_scalar()

        async with dbaccess.Query[int](
            cursor,
            """SELECT id
                 FROM changesets
                WHERE repository={repository}
                  AND to_commit={to_commit}
                  AND from_commit={from_commit}
                  AND for_merge IS NULL
                  AND is_replay={conflicts}""",
            repository=self.to_commit.repository,
            to_commit=self.to_commit,
            from_commit=self.from_commit,
            conflicts=self.conflicts,
        ) as result:
            return await result.maybe_scalar()


class MergeChangesetIds(NamedTuple):
    primary: int
    reference: int


class FindMergeChangesetIds:
    def __init__(
        self,
        parent: api.commit.Commit,
        merge: api.commit.Commit,
    ):
        self.parent = parent
        self.merge = merge

    @property
    def table_names(self) -> Collection[str]:
        return ()

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> Optional[MergeChangesetIds]:
        async with dbaccess.Query[Tuple[int, int]](
            cursor,
            """SELECT to_commit, id
                 FROM changesets
                WHERE repository={repository}
                  AND {parent} IN (from_commit, to_commit)
                  AND for_merge={merge}""",
            repository=self.merge.repository,
            parent=self.parent,
            merge=self.merge,
        ) as result:
            changeset_ids = dict(await result.all())
        if changeset_ids:
            return MergeChangesetIds(
                changeset_ids[self.merge.id], changeset_ids[self.parent.id]
            )
        return None


class MergeChangesets(NamedTuple):
    primary: api.changeset.Changeset
    reference: api.changeset.Changeset


class CreateChangeset(
    CreateAPIObject[api.changeset.Changeset], api_module=api.changeset
):
    @staticmethod
    async def ensure(
        transaction: TransactionBase,
        from_commit: Optional[api.commit.Commit],
        to_commit: api.commit.Commit,
        conflicts: bool,
    ) -> api.changeset.Changeset:
        if (
            changeset_id := await transaction.execute(
                FindChangesetId(from_commit, to_commit, conflicts)
            )
        ) is not None:
            return await api.changeset.fetch(transaction.critic, changeset_id)

        return await CreateChangeset(transaction).insert(
            repository=to_commit.repository,
            from_commit=from_commit,
            to_commit=to_commit,
            is_replay=conflicts,
        )

    @staticmethod
    async def ensureMerge(
        transaction: TransactionBase,
        parent: api.commit.Commit,
        merge: api.commit.Commit,
    ) -> MergeChangesets:
        critic = transaction.critic
        if (
            changeset_ids := await transaction.execute(
                FindMergeChangesetIds(parent, merge)
            )
        ) :
            primary = await api.changeset.fetch(critic, changeset_ids.primary)
            reference = await api.changeset.fetch(critic, changeset_ids.reference)
        else:
            repository = merge.repository
            mergebase = await repository.mergeBase(merge)

            primary = await CreateChangeset(transaction).insert(
                repository=repository,
                from_commit=parent,
                to_commit=merge,
                for_merge=merge,
            )
            reference = await CreateChangeset(transaction).insert(
                repository=repository,
                from_commit=mergebase,
                to_commit=parent,
                for_merge=merge,
            )

        return MergeChangesets(primary, reference)
