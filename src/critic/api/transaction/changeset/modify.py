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

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

from .. import Item, Modifier, Transaction
from . import CreatedChangeset

from critic import api
from critic import dbaccess


class ModifyChangeset(Modifier[api.changeset.Changeset, CreatedChangeset]):
    def requestContent(self) -> ModifyChangeset:
        self.transaction.items.append(RequestContent(self))
        return self

    def requestHighlight(self) -> ModifyChangeset:
        self.transaction.items.append(RequestHighlight(self))
        return self

    @staticmethod
    async def ensure(
        transaction: Transaction,
        from_commit: Optional[api.commit.Commit],
        to_commit: api.commit.Commit,
        conflicts: bool,
    ) -> ModifyChangeset:
        from .ensure import ensure_changeset

        return await ensure_changeset(transaction, from_commit, to_commit, conflicts)


class RequestContent(Item):
    def __init__(self, modifier: ModifyChangeset):
        self.modifier = modifier

    @property
    def key(self) -> tuple:
        return (RequestContent, self.modifier)

    async def __call__(
        self, transaction: Transaction, cursor: dbaccess.TransactionCursor
    ) -> None:
        complete: Optional[bool]

        async with dbaccess.Query[bool](
            cursor,
            """SELECT cscd.complete
                 FROM changesetcontentdifferences AS cscd
                 JOIN changesethighlightrequests AS cshlr ON (
                        cshlr.changeset=cscd.changeset
                      )
                WHERE cscd.changeset={changeset}""",
            changeset=self.modifier.subject,
        ) as result:
            try:
                complete = await result.scalar()
            except cursor.ZeroRowsInResult:
                complete = None

        if complete:
            logger.debug("refreshing content difference request")
            await cursor.execute(
                """UPDATE changesetcontentdifferences
                      SET requested=NOW()
                    WHERE changeset={changeset}""",
                changeset=self.modifier.subject,
            )
        elif complete is None:
            logger.debug("inserting new content difference request")
            await cursor.execute(
                """INSERT
                     INTO changesetcontentdifferences (changeset)
                   VALUES ({changeset})""",
                changeset=self.modifier.subject,
            )
            if not self.modifier.is_created:
                self.modifier.updates["content_requested"] = True


class RequestHighlight(Item):
    def __init__(self, modifier: ModifyChangeset):
        self.modifier = modifier

    @property
    def key(self) -> tuple:
        return (RequestHighlight, self.modifier)

    async def __call__(
        self, transaction: Transaction, cursor: dbaccess.TransactionCursor
    ) -> None:
        requested: Optional[bool]
        evaluated: Optional[bool]

        async with dbaccess.Query[Tuple[bool, bool]](
            cursor,
            """SELECT requested, evaluated
                 FROM changesethighlightrequests
                WHERE changeset={changeset}""",
            changeset=self.modifier.subject,
        ) as state_result:
            try:
                (requested, evaluated) = await state_result.one()
            except cursor.ZeroRowsInResult:
                requested = evaluated = None

        updated = False

        if requested is None:
            logger.debug("inserting new changeset highlight request")
            await cursor.execute(
                """INSERT
                     INTO changesethighlightrequests (changeset, requested)
                   VALUES ({changeset}, TRUE)""",
                changeset=self.modifier.subject,
            )
            updated = True
        elif evaluated:
            async with dbaccess.Query[int](
                cursor,
                """SELECT hlf.id
                     FROM changesetfiledifferences AS csfd
                     JOIN highlightfiles AS hlf ON (
                            hlf.id=csfd.old_highlightfile OR
                            hlf.id=csfd.new_highlightfile
                          )
                    WHERE csfd.changeset={changeset}
                      AND NOT hlf.highlighted
                      AND NOT hlf.requested""",
                changeset=self.modifier.subject,
            ) as files_result:
                non_highlighted_ids = await files_result.scalars()

            if non_highlighted_ids:
                logger.debug("re-requesting highlight request files")
                await cursor.execute(
                    """UPDATE highlightfiles
                          SET requested=TRUE
                        WHERE {id=non_highlighted_ids:array}""",
                    non_highlighted_ids=non_highlighted_ids,
                )
                updated = True
        elif not requested:
            logger.debug("re-requesting highlight request")
            await cursor.execute(
                """UPDATE changesethighlightrequests
                      SET requested=TRUE
                    WHERE changeset={changeset}""",
                changeset=self.modifier.subject,
            )
            updated = True

        if updated and not self.modifier.is_created:
            self.modifier.updates["highlight_requested"] = True
