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

import logging
import re
from typing import Collection, Dict, Literal, Optional, TypedDict

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import textutils
from critic.gitaccess import SHA1


PendingRefUpdateState = Literal["preliminary", "processed", "finished", "failed"]
RefUpdate = TypedDict(
    "RefUpdate", {"ref_name": str, "old_sha1": SHA1, "new_sha1": SHA1}
)


class ValidateError:
    def __init__(self, title: str, message: Optional[str] = None):
        self.title = title
        self.message = message

    def __str__(self) -> str:
        return self.title


Flags = Dict[str, dbaccess.SQLValue]


def reflow(text: str, *, hanging_indent: int = 0) -> str:
    """Reflow text to a line length suitable for Git hook output"""
    return textutils.reflow(
        text, line_length=80 - len("remote: "), hanging_indent=hanging_indent
    )


def is_review_branch(branch_name: str) -> bool:
    pattern = api.critic.settings().repositories.review_branch_pattern
    return re.match(pattern, branch_name) is not None


async def find_tracked_branch(
    repository: api.repository.Repository, name: str
) -> Optional[api.trackedbranch.TrackedBranch]:
    try:
        return await api.trackedbranch.fetch(
            repository.critic, repository=repository, name=name
        )
    except api.trackedbranch.NotFound:
        return None


class EmitOutput:
    def __init__(
        self,
        pendingrefupdate_id: Optional[int],
        output: Optional[str],
        error: Optional[str] = None,
    ):
        self.pendingrefupdate_id = pendingrefupdate_id
        self.output = output
        self.error = error

    @property
    def table_names(self) -> Collection[str]:
        return ("pendingrefupdateoutputs",)

    async def __call__(
        self,
        transaction: api.transaction.TransactionBase,
        cursor: dbaccess.TransactionCursor,
    ) -> None:
        if self.pendingrefupdate_id is None:
            return
        output = self.output
        if self.error is not None:
            async with dbaccess.Query[int](
                cursor,
                """SELECT updater
                    FROM pendingrefupdates
                    WHERE id={pendingrefupdate_id}""",
                pendingrefupdate_id=self.pendingrefupdate_id,
            ) as result:
                try:
                    updater_id = await result.scalar()
                except dbaccess.ZeroRowsInResult:
                    # See comment below.
                    return
            updater: Optional[api.user.User]
            if updater_id is not None:
                updater = await api.user.fetch(transaction.critic, updater_id)
            else:
                updater = None
            if not updater or updater.hasRole("developer"):
                output = self.error
        if (output and output.strip()) or self.error:
            # It's possible that the row in |pendingrefupdate| has already been
            # deleted, so use INSERT INTO/SELECT to avoid violating constraints
            # when inserting rows into |pendingrefupdateoutputs|.
            await cursor.execute(
                """INSERT
                    INTO pendingrefupdateoutputs (pendingrefupdate, output)
                SELECT id, {output}
                    FROM pendingrefupdates
                    WHERE id={pendingrefupdate_id}""",
                output=output,
                pendingrefupdate_id=self.pendingrefupdate_id,
            )


async def emit_output(
    critic: api.critic.Critic,
    pendingrefupdate_id: Optional[int],
    output: Optional[str],
    error: Optional[str] = None,
) -> None:
    async with api.transaction.start(critic) as transaction:
        await transaction.execute(EmitOutput(pendingrefupdate_id, output, error))


class SetPendingRefUpdateState:
    def __init__(
        self,
        pendingrefupdate_id: Optional[int],
        from_state: PendingRefUpdateState,
        to_state: PendingRefUpdateState,
    ):
        self.pendingrefupdate_id = pendingrefupdate_id
        self.from_state = from_state
        self.to_state = to_state

    @property
    def table_names(self) -> Collection[str]:
        return ("pendingrefupdates",)

    async def __call__(
        self,
        transaction: api.transaction.TransactionBase,
        cursor: dbaccess.TransactionCursor,
    ) -> None:
        if self.pendingrefupdate_id is None:
            return
        await cursor.execute(
            """UPDATE pendingrefupdates
                  SET state={to_state}
                WHERE id={pendingrefupdate_id}
                  AND state={from_state}""",
            pendingrefupdate_id=self.pendingrefupdate_id,
            from_state=self.from_state,
            to_state=self.to_state,
        )
