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
from typing import Optional, List, Union

logger = logging.getLogger(__name__)

from . import CreatedBatch, CreatedReviewEvent
from .updatereviewfiles import UpdateReviewFiles
from .updatereviewtags import UpdateReviewTags
from .. import Transaction, Query, Insert, Item
from ..comment import CreatedComment

from critic import api
from critic import dbaccess


class PerformCommentChainsChanges(Item):
    def __init__(self, batch: CreatedBatch, user: api.user.User):
        self.batch = batch
        self.user = user

    async def __call__(
        self, _: Transaction, cursor: dbaccess.TransactionCursor
    ) -> None:
        morphed_comments: List[dbaccess.Parameters] = []
        closed_issues: List[dbaccess.Parameters] = []
        reopened_issues: List[dbaccess.Parameters] = []

        async with cursor.query(
            """SELECT chain, to_type, from_state, to_state, to_last_commit,
                    to_addressed_by
                FROM commentchainchanges
                WHERE batch={batch}
                AND state='performed'""",
            batch=self.batch,
        ) as result:
            async for (
                comment_id,
                to_type,
                from_state,
                to_state,
                to_last_commit,
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
    transaction: Transaction,
    review: api.review.Review,
    batch_comment: Optional[CreatedComment],
) -> CreatedBatch:
    critic = transaction.critic
    user = critic.effective_user

    unpublished_changes = await api.batch.fetchUnpublished(review)

    if await unpublished_changes.is_empty:
        raise api.batch.Error("No unpublished changes to submit")

    created_comments: List[Union[api.comment.Comment, CreatedComment]] = []
    empty_comments = []

    if batch_comment:
        created_comments.append(batch_comment)

    for comment in await unpublished_changes.created_comments:
        if comment.text.strip():
            created_comments.append(comment)
        else:
            empty_comments.append(comment)

    logger.debug("created_comments=%r", created_comments)
    logger.debug("empty_comments=%r", empty_comments)

    event = CreatedReviewEvent.ensure(transaction, review, "batch")
    batch = CreatedBatch(transaction, review)

    transaction.items.append(
        Insert("batches", returning="id", collector=batch).values(
            event=event, comment=batch_comment,
        )
    )

    transaction.tables.add("commentchains")
    transaction.items.append(
        Query(
            """UPDATE commentchains
                  SET batch={batch}
                WHERE {id=created_comments:array}""",
            batch=batch,
            created_comments=created_comments,
        )
    )
    transaction.items.append(
        Query(
            """DELETE
                 FROM commentchains
                WHERE {id=empty_comments:array}""",
            empty_comments=empty_comments,
        )
    )

    transaction.tables.add("comments")
    transaction.items.append(
        Query(
            """UPDATE comments
                  SET batch={batch}
                WHERE {id=written_replies:array}""",
            batch=batch,
            written_replies=list(await unpublished_changes.written_replies),
        )
    )

    transaction.tables.add("commentchainlines")
    transaction.items.append(
        Query(
            """UPDATE commentchainlines
                  SET state='current'
                WHERE {chain=created_comments:array}""",
            created_comments=created_comments,
        )
    )

    resolved_issues = await unpublished_changes.resolved_issues
    reopened_issues = await unpublished_changes.reopened_issues
    morphed_comments = await unpublished_changes.morphed_comments

    # Lock all rows in |commentchains| that we may want to update.
    for issue in resolved_issues:
        transaction.lock("commentchains", id=issue.id)
    for issue in reopened_issues:
        transaction.lock("commentchains", id=issue.id)
    for comment in morphed_comments.keys():
        transaction.lock("commentchains", id=comment.id)

    # Mark valid comment state changes as performed.
    transaction.tables.add("commentchainchanges")
    transaction.items.append(
        Query(
            """UPDATE commentchainchanges
                  SET batch={batch},
                      state='performed'
                WHERE uid={user}
                  AND state='draft'
                  AND chain IN (SELECT id
                                  FROM commentchains
                                 WHERE {id=issues:array}
                                   AND type='issue'
                                   AND state={current_state})""",
            dict(
                batch=batch,
                user=user,
                issues=list(resolved_issues),
                current_state="open",
            ),
            dict(
                batch=batch,
                user=user,
                issues=list(reopened_issues),
                current_state="closed",
            ),
        )
    )
    transaction.items.append(
        Query(
            """UPDATE commentchainchanges
                  SET batch={batch},
                      state='performed'
                WHERE uid={user}
                  AND state='draft'
                  AND chain IN (SELECT id
                                  FROM commentchains
                                  JOIN commentchainchanges ON (chain=id)
                                 WHERE {id=issues:array}
                                   AND type='issue'
                                   AND commentchains.state='addressed'
                                   AND addressed_by=from_addressed_by
                                   AND commentchainchanges.batch IS NULL
                                   AND commentchainchanges.uid={user})""",
            batch=batch,
            user=user,
            issues=list(reopened_issues),
        )
    )

    transaction.tables.add("commentchainlines")
    transaction.items.append(
        Query(
            """UPDATE commentchainlines
                  SET state='current'
                WHERE uid={user}
                  AND state='draft'
                  AND chain IN (SELECT chain
                                  FROM commentchainchanges
                                 WHERE batch={batch}
                                   AND state='performed'
                                   AND from_state='addressed')""",
            user=user,
            batch=batch,
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
    transaction.items.append(
        Query(
            """UPDATE commentchainchanges
                  SET batch={batch},
                      state='performed'
                WHERE uid={user}
                  AND state='draft'
                  AND chain IN (SELECT id
                                  FROM commentchains
                                 WHERE {id=comments:array}
                                   AND type={current_type})""",
            dict(
                batch=batch, user=user, comments=morphed_to_issue, current_type="note"
            ),
            dict(
                batch=batch, user=user, comments=morphed_to_note, current_type="issue"
            ),
        )
    )

    # Actually perform state changes marked as valid above.
    # transaction.items.append(Query(
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

    transaction.items.append(PerformCommentChainsChanges(batch, user))

    reviewed_file_changes = await unpublished_changes.reviewed_file_changes
    unreviewed_file_changes = await unpublished_changes.unreviewed_file_changes

    # Lock all rows in |reviewfiles| that we may want to update.
    transaction.tables.add("reviewfilechanges")
    for rfc in reviewed_file_changes:
        transaction.lock("reviewfilechanges", file=rfc.id)
    for rfc in unreviewed_file_changes:
        transaction.lock("reviewfilechanges", file=rfc.id)

    # Mark valid draft changes as "performed".
    transaction.items.append(
        Query(
            """UPDATE reviewfilechanges
                  SET batch={batch},
                      state='performed'
                WHERE uid={user}
                  AND state='draft'
                  AND file IN (SELECT file
                                 FROM reviewuserfiles
                                WHERE {file=files:array}
                                  AND reviewed={current_reviewed})""",
            dict(
                batch=batch,
                user=user,
                current_reviewed=False,
                files=list(reviewed_file_changes),
            ),
            dict(
                batch=batch,
                user=user,
                current_reviewed=True,
                files=list(unreviewed_file_changes),
            ),
        )
    )

    # Actually perform all the changes we previously marked as performed.
    transaction.tables.add("reviewuserfiles")
    transaction.items.append(
        Query(
            """UPDATE reviewuserfiles
                  SET reviewed={new_reviewed}
                WHERE file IN (
                   SELECT file
                     FROM reviewfilechanges
                    WHERE batch={batch}
                      AND state='performed'
                      AND to_reviewed={new_reviewed}
                      )
                  AND uid={user}""",
            dict(user=user, batch=batch, new_reviewed=True),
            dict(user=user, batch=batch, new_reviewed=False),
        )
    )

    transaction.items.append(UpdateReviewFiles(review))
    transaction.finalizers.add(UpdateReviewTags(review))

    return batch
