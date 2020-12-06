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
from typing import Collection, Optional, List

logger = logging.getLogger(__name__)

from . import CreatedBatch, CreateReviewEvent
from .updatereviewfiles import UpdateReviewFiles
from .updatereviewtags import UpdateReviewTags
from ..item import Lock, SubQuery, Update, Delete
from ..base import TransactionBase

from critic import api
from critic import dbaccess


class PerformCommentChainsChanges:
    def __init__(self, batch: api.batch.Batch, user: api.user.User):
        self.batch = batch
        self.user = user

    @property
    def table_names(self) -> Collection[str]:
        return ("commentchains",)

    async def __call__(
        self, _: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> None:
        morphed_comments: List[dbaccess.Parameters] = []
        closed_issues: List[dbaccess.Parameters] = []
        reopened_issues: List[dbaccess.Parameters] = []

        async with cursor.query(
            """SELECT chain, to_type, to_state, to_addressed_by
                 FROM commentchainchanges
                WHERE batch={batch}
                  AND state='performed'""",
            batch=self.batch,
        ) as result:
            async for (
                comment_id,
                to_type,
                to_state,
                to_addressed_by,
            ) in result:
                if to_type is not None:
                    assert to_state is None
                    morphed_comments.append(
                        dict(comment_id=comment_id, new_type=to_type)
                    )
                else:
                    assert to_state is not None
                    if to_state == "closed":
                        closed_issues.append(
                            dict(comment_id=comment_id, user=self.user)
                        )
                    else:
                        reopened_issues.append(
                            dict(
                                comment_id=comment_id,
                                new_state=to_state,
                                new_addressed_by=to_addressed_by,
                            )
                        )

        logger.debug("reopened_issues=%r", reopened_issues)

        await cursor.executemany(
            """UPDATE commentchains
                SET type={new_type}
                WHERE id={comment_id}""",
            morphed_comments,
        )
        await cursor.executemany(
            """UPDATE commentchains
                SET state='closed',
                    closed_by={user}
                WHERE id={comment_id}""",
            closed_issues,
        )
        await cursor.executemany(
            """UPDATE commentchains
                SET state={new_state},
                    addressed_by={new_addressed_by},
                    addressed_by_update=NULL
                WHERE id={comment_id}""",
            reopened_issues,
        )


async def submit_changes(
    transaction: TransactionBase,
    review: api.review.Review,
    unpublished_batch: api.batch.Batch,
    batch_comment: Optional[api.comment.Comment],
) -> api.batch.Batch:
    critic = transaction.critic
    author = await unpublished_batch.author

    # This mechanism is used (inside a SAVEPOINT) to calculate whether the
    # review would be accepted after submitting changes. When doing so, the
    # calculation will be performed for all review users (with unpublished
    # changes) regardless of which user triggered the calculation.
    if not transaction.has_savepoint:
        api.PermissionDenied.raiseUnlessUser(critic, author)

    if not unpublished_batch.is_unpublished:
        raise api.batch.Error("Batch is not unpublished")
    if await unpublished_batch.is_empty:
        raise api.batch.Error("No unpublished changes to submit")

    created_comments: List[api.comment.Comment] = []
    empty_comments = []

    if batch_comment:
        created_comments.append(batch_comment)

    for comment in await unpublished_batch.created_comments:
        if comment.text.strip():
            created_comments.append(comment)
        else:
            empty_comments.append(comment)

    logger.debug("created_comments=%r", created_comments)
    logger.debug("empty_comments=%r", empty_comments)

    created_batch = await CreatedBatch(transaction, review).insert(
        event=await CreateReviewEvent.ensure(transaction, review, "batch"),
        comment=batch_comment,
    )

    await transaction.execute(
        Update("commentchains").set(batch=created_batch).where(id=created_comments)
    )
    await transaction.execute(Delete("commentchains").where(id=empty_comments))

    written_replies = list(await unpublished_batch.written_replies)
    await transaction.execute(
        Update("comments").set(batch=created_batch).where(id=written_replies)
    )

    await transaction.execute(
        Update("commentchainlines").set(state="current").where(chain=created_comments)
    )

    resolved_issues = await unpublished_batch.resolved_issues
    reopened_issues = await unpublished_batch.reopened_issues
    morphed_comments = await unpublished_batch.morphed_comments

    # Lock all rows in |commentchains| that we may want to update.
    for issue in resolved_issues:
        await transaction.lock("commentchains", id=issue.id)
    for issue in reopened_issues:
        await transaction.lock("commentchains", id=issue.id)
    for comment in morphed_comments.keys():
        await transaction.lock("commentchains", id=comment.id)

    async with api.critic.Query[int](
        critic,
        """
        SELECT id
          FROM commentchains
         WHERE {id=issues:array}
           AND type='issue'
           AND state='open'
        """,
        issues=list(resolved_issues),
    ) as result:
        resolved_issue_ids = await result.scalars()

    async with api.critic.Query[int](
        critic,
        """
        SELECT id
          FROM commentchains
         WHERE {id=issues:array}
           AND type='issue'
           AND state='closed'
        """,
        issues=list(reopened_issues),
    ) as result:
        reopened_resolved_issue_ids = await result.scalars()

    async with api.critic.Query[int](
        critic,
        """
        SELECT id
          FROM commentchains
          JOIN commentchainchanges ON (chain=id)
         WHERE {id=issues:array}
           AND type='issue'
           AND commentchains.state='addressed'
           AND addressed_by=from_addressed_by
           AND commentchainchanges.batch IS NULL
           AND commentchainchanges.uid={user}
        """,
        issues=list(reopened_issues),
        user=author,
    ) as result:
        reopened_addressed_issue_ids = await result.scalars()

    # Mark valid comment state changes as performed.
    if (
        resolved_issue_ids
        or reopened_resolved_issue_ids
        or reopened_addressed_issue_ids
    ):
        await transaction.execute(
            Update("commentchainchanges")
            .set(batch=created_batch, state="performed")
            .where(
                uid=author,
                state="draft",
                chain=[
                    *resolved_issue_ids,
                    *reopened_resolved_issue_ids,
                    *reopened_addressed_issue_ids,
                ],
            )
        )

    await transaction.execute(
        Update("commentchainlines")
        .set(state="current")
        .where(
            uid=author,
            state="draft",
            chain=SubQuery(
                """
                SELECT chain
                  FROM commentchainchanges
                 WHERE batch={batch}
                   AND state='performed'
                   AND from_state='addressed'
                """,
                batch=created_batch,
            ),
        )
    )

    # Mark valid comment type changes as performed.
    morphed_to_issue = []
    morphed_to_note = []
    for comment, new_type in morphed_comments.items():
        if new_type == "issue":
            morphed_to_issue.append(comment)
        else:
            morphed_to_note.append(comment)
    await transaction.execute(
        Update("commentchainchanges")
        .set(batch=created_batch, state="performed")
        .where(
            uid=author,
            state="draft",
            chain=SubQuery(
                """
                SELECT id
                  FROM commentchains
                 WHERE id=ANY ({comments})
                   AND type='note'
                """,
                comments=morphed_to_issue,
            ),
        )
    )
    await transaction.execute(
        Update("commentchainchanges")
        .set(batch=created_batch, state="performed")
        .where(
            uid=author,
            state="draft",
            chain=SubQuery(
                """
                SELECT id
                  FROM commentchains
                 WHERE id=ANY ({comments})
                   AND type='issue'
                """,
                comments=morphed_to_note,
            ),
        )
    )

    # Actually perform state changes marked as valid above.
    # transaction.execute(Query(
    #     """UPDATE commentchains
    #           SET state={new_state},
    #               closed_by={closed_by}
    #         WHERE id IN (SELECT chain
    #                        FROM commentchainchanges
    #                       WHERE batch={batch}
    #                         AND state='performed'
    #                         AND to_state={new_state}
    #                         AND from_state={old_state})""",
    #     dict(batch=batch, new_state="closed", old_state="open",
    #          closed_by=user),
    #     dict(batch=batch, new_state="open", old_state="closed",
    #          closed_by=None)))

    await transaction.execute(PerformCommentChainsChanges(created_batch, author))

    reviewed_file_changes = await unpublished_batch.reviewed_file_changes
    unreviewed_file_changes = await unpublished_batch.unreviewed_file_changes

    logger.debug(f"{reviewed_file_changes=}")
    logger.debug(f"{unreviewed_file_changes=}")

    # Lock all rows in |reviewfiles| that we may want to update.
    for rfc in reviewed_file_changes:
        await transaction.execute(Lock(rfc))
    for rfc in unreviewed_file_changes:
        await transaction.execute(Lock(rfc))

    # Mark valid draft changes as "performed".
    await transaction.execute(
        Update("reviewfilechanges")
        .set(batch=created_batch, state="performed")
        .where(
            uid=author,
            state="draft",
            file=SubQuery(
                """
                SELECT file
                  FROM reviewuserfiles
                 WHERE (file=ANY ({reviewed_files}) AND NOT reviewed)
                    OR (file=ANY ({unreviewed_files}) AND reviewed)
                """,
                reviewed_files=list(reviewed_file_changes),
                unreviewed_files=list(unreviewed_file_changes),
            ),
        )
    )

    # Actually perform all the changes we previously marked as performed.
    await transaction.execute(
        Update("reviewuserfiles")
        .set(reviewed=True)
        .where(
            uid=author,
            file=SubQuery(
                """
                SELECT file
                  FROM reviewfilechanges
                 WHERE batch={batch}
                   AND state='performed'
                   AND to_reviewed
                """,
                batch=created_batch,
            ),
        )
    )
    await transaction.execute(
        Update("reviewuserfiles")
        .set(reviewed=False)
        .where(
            uid=author,
            file=SubQuery(
                """
                SELECT file
                  FROM reviewfilechanges
                 WHERE batch={batch}
                   AND state='performed'
                   AND NOT to_reviewed
                """,
                batch=created_batch,
            ),
        )
    )

    await transaction.execute(UpdateReviewFiles(review))
    transaction.finalizers.add(UpdateReviewTags(review))

    return created_batch
