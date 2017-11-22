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

from typing import Optional, Union


from .. import Item, Transaction
from . import CreatedChangeset
from .modify import ModifyChangeset

from critic import api
from critic import dbaccess


async def find_changeset_id(
    cursor: dbaccess.BasicCursor,
    from_commit: Optional[api.commit.Commit],
    to_commit: api.commit.Commit,
    conflicts: bool,
) -> Optional[int]:
    if from_commit is None:
        async with dbaccess.Query[int](
            cursor,
            """SELECT id
                    FROM changesets
                WHERE repository={repository}
                    AND to_commit={to_commit}
                    AND from_commit IS NULL
                    AND for_merge IS NULL""",
            repository=to_commit.repository,
            to_commit=to_commit,
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
        repository=to_commit.repository,
        to_commit=to_commit,
        from_commit=from_commit,
        conflicts=conflicts,
    ) as result:
        return await result.maybe_scalar()


class CreateChangeset(Item):
    def __init__(
        self,
        created_changeset: CreatedChangeset,
        from_commit: Optional[api.commit.Commit],
        to_commit: api.commit.Commit,
        conflicts: bool,
    ):
        self.created_changeset = created_changeset
        self.from_commit = from_commit
        self.to_commit = to_commit
        self.conflicts = conflicts

    @property
    def key(self) -> tuple:
        return (CreateChangeset, self.from_commit, self.to_commit, self.conflicts)

    async def __call__(
        self, transaction: Transaction, cursor: dbaccess.TransactionCursor
    ) -> None:
        if (
            changeset_id := await find_changeset_id(
                cursor, self.from_commit, self.to_commit, self.conflicts
            )
        ) is not None:
            self.created_changeset(changeset_id)
            return

        self.created_changeset.insert(
            repository=self.to_commit.repository,
            from_commit=self.from_commit,
            to_commit=self.to_commit,
            is_replay=self.conflicts,
        )


async def ensure_changeset(
    transaction: Transaction,
    from_commit: Optional[api.commit.Commit],
    to_commit: api.commit.Commit,
    conflicts: bool,
) -> ModifyChangeset:
    if from_commit is not None:
        assert from_commit.repository == to_commit.repository

    repository = to_commit.repository
    critic = repository.critic

    if (
        changeset_id := await find_changeset_id(
            critic.database.cursor(), from_commit, to_commit, conflicts
        )
    ) is not None:
        return ModifyChangeset(
            transaction, await api.changeset.fetch(critic, changeset_id)
        )

    created_changeset = CreatedChangeset(transaction)

    transaction.items.append(
        CreateChangeset(created_changeset, from_commit, to_commit, conflicts)
    )

    return ModifyChangeset(transaction, created_changeset)

    async with critic.transaction() as cursor:
        try:
            if from_commit is None:
                async with cursor.query(
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
                async with cursor.query(
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
            async with cursor.query(
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
