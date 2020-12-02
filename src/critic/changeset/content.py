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

import json
import logging
from typing import Any, Dict, Optional, Sequence, Tuple, cast

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic.gitaccess import SHA1


class FatalErrors(Exception):
    def __init__(self, changeset_id: int, errors: Sequence[Any]):
        super(FatalErrors, self).__init__(
            "%d errors encountered while processing changeset %d."
            % (len(errors), changeset_id)
        )
        self.changeset_id = changeset_id
        self.errors = errors


async def check_syntax_highlighting(
    critic: api.critic.Critic, changeset_id: int
) -> bool:
    # Check if all syntax highlight files actually exist.  We should never
    # delete them without updating the database to match, but since they are
    # typically stored under /var/cache, it's possible the system administrator
    # did to free up space, or that they were skipped during a system migration.
    # This should be safe per LSB, so make it so.

    # async with api.critic.Query[bool](
    #     critic,
    #     """SELECT is_replay
    #          FROM changesets
    #         WHERE id={changeset_id}""",
    #     changeset_id=changeset_id,
    # ) as conflicts_result:
    #     conflicts = await conflicts_result.scalar()

    async with api.critic.Query[Tuple[SHA1, int]](
        critic,
        """SELECT sha1, language
             FROM highlightfiles
             JOIN highlightlanguages ON (id=language)
            WHERE changeset={changeset}
              AND NOT highlighted""",
        changeset=changeset_id,
    ) as highlight_files_result:
        # FIXME: Somewhat unfortunate to be reproducing difference engine job
        # keys here, given how internal to its implementation they really are.
        highlight_files = await highlight_files_result.all()

    missing_job_keys = [
        json.dumps(["SyntaxHighlightFile", changeset_id, sha1, language_id])
        for sha1, language_id in highlight_files
    ]

    if not missing_job_keys:
        # All files are there.
        return True

    async with api.critic.Query[int](
        critic,
        """SELECT COUNT(*)
             FROM changeseterrors
            WHERE changeset={changeset}
              AND {job_key=missing_job_keys:array}""",
        changeset=changeset_id,
        missing_job_keys=missing_job_keys,
    ) as errors_result:
        had_errors = await errors_result.scalar()

    # Return true ("all okay") if all missing files had errors.
    return len(missing_job_keys) == had_errors


async def request(
    critic: api.critic.Critic,
    changeset_id: int,
    *,
    request_highlight: bool = True,
    in_transaction: Optional[dbaccess.TransactionCursor] = None
):
    async def update_database(
        cursor: dbaccess.TransactionCursor,
    ) -> Tuple[bool, bool, bool]:
        content_difference_complete: Optional[bool] = False
        syntax_highlight_requested: Optional[bool] = False
        syntax_highlight_evaluated: Optional[bool] = False
        syntax_highlight_complete: Optional[bool] = False
        wakeup_difference_engine: bool = False

        # Check if the content difference has been requested already, and if so
        # whether it is complete.  Also update the |requested| timestamp, if
        # it's been completed.
        async with dbaccess.Query[Tuple[bool, bool, bool]](
            cursor,
            """SELECT cscd.complete, cshlr.requested, cshlr.evaluated
                 FROM changesetcontentdifferences AS cscd
                 JOIN changesethighlightrequests AS cshlr ON (
                        cshlr.changeset=cscd.changeset
                      )
                WHERE cscd.changeset={changeset}""",
            changeset=changeset_id,
        ) as result:
            try:
                (
                    content_difference_complete,
                    syntax_highlight_requested,
                    syntax_highlight_evaluated,
                ) = await result.one()
            except cursor.ZeroRowsInResult:
                content_difference_complete = (
                    syntax_highlight_requested
                ) = syntax_highlight_evaluated = None

        if content_difference_complete:
            await cursor.execute(
                """UPDATE changesetcontentdifferences
                      SET requested=NOW()
                    WHERE changeset={changeset}""",
                changeset=changeset_id,
            )

        if content_difference_complete is None:
            # Otherwise, insert a new row to request the content difference, and
            # wake the difference engine process from its sleep.
            await cursor.execute(
                """INSERT
                     INTO changesetcontentdifferences (changeset)
                   VALUES ({changeset})""",
                changeset=changeset_id,
            )
            await cursor.execute(
                """INSERT
                     INTO changesethighlightrequests (changeset, requested)
                   VALUES ({changeset}, {requested})""",
                changeset=changeset_id,
                requested=request_highlight,
            )
            content_difference_complete = False
            wakeup_difference_engine = True

        if request_highlight:
            if syntax_highlight_evaluated:
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
                    changeset=changeset_id,
                ) as non_highlighted_ids_result:
                    non_highlighted_ids = await non_highlighted_ids_result.scalars()

                if non_highlighted_ids:
                    await cursor.execute(
                        """UPDATE highlightfiles
                              SET requested=TRUE
                            WHERE {id=non_highlighted_ids:array}""",
                        non_highlighted_ids=non_highlighted_ids,
                    )
                    wakeup_difference_engine = True
                else:
                    syntax_highlight_complete = True
            elif not syntax_highlight_requested:
                await cursor.execute(
                    """UPDATE changesethighlightrequests
                          SET requested=TRUE
                        WHERE changeset={changeset}""",
                    changeset=changeset_id,
                )
                wakeup_difference_engine = True
        else:
            # Pretend it's complete, so that it doesn't affect the return value.
            syntax_highlight_complete = True

        return (
            bool(content_difference_complete),
            bool(syntax_highlight_complete),
            wakeup_difference_engine,
        )

    if in_transaction:
        (
            content_difference_complete,
            syntax_highlight_complete,
            wakeup_difference_engine,
        ) = await update_database(in_transaction)
    else:
        async with critic.transaction() as cursor:
            (
                content_difference_complete,
                syntax_highlight_complete,
                wakeup_difference_engine,
            ) = await update_database(cursor)

    if wakeup_difference_engine:
        await critic.wakeup_service("differenceengine")

    return content_difference_complete and syntax_highlight_complete


async def progress_single(critic: api.critic.Critic, changeset_id: int) -> Any:
    async with api.critic.Query[bool](
        critic,
        """SELECT complete
             FROM changesets
            WHERE id={changeset_id}""",
        changeset_id=changeset_id,
    ) as result:
        structure_difference_complete = await result.scalar()

    async with api.critic.Query[bool](
        critic,
        """SELECT complete
             FROM changesetcontentdifferences
            WHERE changeset={changeset_id}""",
        changeset_id=changeset_id,
    ) as result:
        try:
            content_difference_complete = await result.scalar()
            content_difference_requested = True
        except result.ZeroRowsInResult:
            content_difference_complete = False
            content_difference_requested = False

    async with api.critic.Query[bool](
        critic,
        """SELECT complete
             FROM changesethighlightrequests
            WHERE changeset={changeset_id}""",
        changeset_id=changeset_id,
    ) as result:
        try:
            syntax_highlight_complete = await result.scalar()
            syntax_highlight_requested = True
        except result.ZeroRowsInResult:
            syntax_highlight_complete = False
            syntax_highlight_requested = False

    # Count total and examined files.
    async with api.critic.Query[Tuple[int, int]](
        critic,
        """SELECT COUNT(changesetfiles.changeset),
                  COUNT(changesetfiledifferences.changeset)
             FROM changesetfiles
  LEFT OUTER JOIN changesetfiledifferences USING (changeset, file)
            WHERE changesetfiles.changeset={changeset_id}""",
        changeset_id=changeset_id,
    ) as files_result:
        total_files, examined_files = await files_result.one()

    # Count examined but not compared files.
    async with api.critic.Query[int](
        critic,
        """SELECT COUNT(changesetmodifiedregularfiles.changeset)
             FROM changesetfiledifferences
            WHERE changesetfiledifferences.changeset={changeset_id}
              AND changesetfiledifferences.comparison_pending""",
        changeset_id=changeset_id,
    ) as uncompared_files_result:
        uncompared_files = await uncompared_files_result.scalar()

    # Content difference is usable if structure difference is complete and all
    # files are examined and compared.
    content_difference_usable = (
        structure_difference_complete
        and examined_files == total_files
        and uncompared_files == 0
    )

    # Count total and analyzed blocks of changed lines.
    async with api.critic.Query[Tuple[int, int]](
        critic,
        """SELECT COUNT(changesetchangedlines.changeset),
                  COUNT(changesetchangedlines.analysis)
             FROM changesetchangedlines
            WHERE changesetchangedlines.changeset={changeset_id}
              AND changesetchangedlines.delete_length>0
              AND changesetchangedlines.insert_length>0""",
        changeset_id=changeset_id,
    ) as blocks_result:
        total_blocks, analyzed_blocks = await blocks_result.one()

    content_difference = {
        "complete": content_difference_complete,
        "requested": content_difference_requested,
        "usable": content_difference_usable,
        "total_files": total_files,
        "unexamined_files": total_files - examined_files,
        "uncompared_files": uncompared_files,
        "total_blocks": total_blocks,
        "unanalyzed_blocks": total_blocks - analyzed_blocks,
    }

    total_versions = unfinished_versions = 0

    async with api.critic.Query[Tuple[bool, int]](
        critic,
        """SELECT highlighted, COUNT(*)
             FROM highlightfiles
             JOIN changesetfiledifferences ON (
                    highlightfiles.id IN (
                      old_highlightfile,
                      new_highlightfile
                    )
                  )
            WHERE changeset={changeset_id}
         GROUP BY highlighted""",
        changeset_id=changeset_id,
    ) as highlighted_result:
        async for is_highlighted, count in highlighted_result:
            total_versions += count
            if not is_highlighted:
                unfinished_versions += count

    syntax_highlight = {
        "complete": syntax_highlight_complete,
        "requested": syntax_highlight_requested,
        "usable": True,  # Syntax highlighting is always optional.
        "total_versions": total_versions,
        "unfinished_versions": unfinished_versions,
    }

    return {
        "content_difference": content_difference,
        "syntax_highlight": syntax_highlight,
    }


async def progress(critic: api.critic.Critic, changeset_ids: Sequence[int]) -> Any:
    total_progress = {"changeset_ids": sorted(changeset_ids)}

    def merge(total_values: Any, values: Dict[Any, Any]) -> None:
        for key, value in values.items():
            if isinstance(value, dict):
                merge(total_values.get(key, {}), cast(Dict[Any, Any], value))
            elif isinstance(value, bool):
                total_values[key] = total_values.get(key, True) and value
            else:
                assert isinstance(value, int)
                total_values[key] = total_values.get(key, 0) + value

    for changeset_id in changeset_ids:
        merge(total_progress, await progress_single(critic, changeset_id))

    return total_progress
