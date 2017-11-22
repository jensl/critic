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
from typing import Container, Set

logger = logging.getLogger(__name__)

from . import ReviewUserTag, has_unpublished_changes
from .. import Transaction, Query
from critic import api


async def discard_changes(
    transaction: Transaction,
    review: api.review.Review,
    discard: Container[api.batch.DiscardValue],
) -> None:
    unpublished_changes = await api.batch.fetchUnpublished(review)

    if await unpublished_changes.is_empty:
        return

    author = await unpublished_changes.author

    if "created_comments" in discard:
        transaction.tables.add("commentchains")
        transaction.items.append(
            Query(
                """DELETE
                     FROM commentchains
                    WHERE {id=created_comments:array}""",
                created_comments=list(await unpublished_changes.created_comments),
            )
        )
        transaction.tables.add("comments")
        transaction.items.append(
            Query(
                """DELETE
                     FROM comments
                    WHERE {chain=created_comments:array}""",
                created_comments=list(await unpublished_changes.created_comments),
            )
        )

    if "written_replies" in discard:
        transaction.tables.add("comments")
        transaction.items.append(
            Query(
                """DELETE
                     FROM comments
                    WHERE {id=written_replies:array}""",
                written_replies=list(await unpublished_changes.written_replies),
            )
        )

    modified_comments = set()

    if "resolved_issues" in discard:
        modified_comments.update(await unpublished_changes.resolved_issues)
    if "reopened_issues" in discard:
        modified_comments.update(await unpublished_changes.reopened_issues)
    if "morphed_comments" in discard:
        modified_comments.update(await unpublished_changes.morphed_comments)

    if modified_comments:
        transaction.tables.add("commentchainchanges")
        transaction.items.append(
            Query(
                """DELETE
                     FROM commentchainchanges
                    WHERE uid={author}
                      AND state='draft'
                      AND {chain=modified_comments:array}""",
                author=author,
                modified_comments=list(modified_comments),
            )
        )

    if "reopened_issues" in discard:
        transaction.tables.add("commentchainlines")
        transaction.items.append(
            Query(
                """DELETE
                     FROM commentchainlines
                    WHERE uid={author}
                      AND state='draft'
                      AND {chain=reopened_issues:array}""",
                author=author,
                reopened_issues=list(await unpublished_changes.reopened_issues),
            )
        )

    file_changes: Set[api.reviewablefilechange.ReviewableFileChange] = set()

    if "reviewed_changes" in discard:
        file_changes.update(await unpublished_changes.reviewed_file_changes)
    if "unreviewed_changes" in discard:
        file_changes.update(await unpublished_changes.unreviewed_file_changes)

    if file_changes:
        transaction.tables.add("reviewfilechanges")
        transaction.items.append(
            Query(
                """DELETE
                     FROM reviewfilechanges
                    WHERE uid={author}
                      AND state='draft'
                      AND {file=file_changes:array}""",
                author=author,
                file_changes=list(file_changes),
            )
        )

    ReviewUserTag.ensure(
        transaction, review, author, "unpublished", has_unpublished_changes
    )
