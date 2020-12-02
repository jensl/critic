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
import itertools
from collections import defaultdict
from typing import Set, Dict, Tuple

logger = logging.getLogger(__name__)

from .finalizeassignments import FinalizeAssignments
from ..base import TransactionBase, Finalizer

from critic import api
from critic import dbaccess


async def update_review_tags(
    review: api.review.Review, cursor: dbaccess.TransactionCursor
) -> None:
    """Update the review tags relating to review file assignments

    This includes the |assigned_untaken|, |assigned_primary| and
    |unreviewed_followup| tags."""

    # Set of assigned reviewers.
    #
    #   { |users.id| }
    assigned: Set[int] = set()

    # Users that are assigned to review changes, per file.
    #
    #   { |files.id|: { |users.id| } }
    assigned_per_file: Dict[int, Set[int]] = defaultdict(set)

    # Files with pending changes (not reviewed by any user.)
    #
    #   { |files.id| }
    pending_files: Set[int] = set()

    # Set of reviewers with unseen changes.
    #
    #   { |users.id| }
    unseen: Set[int] = set()

    async with dbaccess.Query[Tuple[int, int, bool, bool]](
        cursor,
        """SELECT reviewuserfiles.uid, reviewfiles.id,
                  NOT reviewfiles.reviewed, reviewuserfiles.reviewed
             FROM reviewuserfiles
             JOIN reviewfiles ON (reviewfiles.id=reviewuserfiles.file)
            WHERE reviewfiles.review={review}""",
        review=review,
    ) as result1:
        # is_pending = no-one has reviewed the change
        # has_reviewed = this user has reviewed it (implies `not is_pending`)
        async for reviewer_id, file_id, is_pending, has_reviewed in result1:
            assigned.add(reviewer_id)
            assigned_per_file[file_id].add(reviewer_id)
            if is_pending:
                pending_files.add(file_id)
            if not has_reviewed:
                unseen.add(reviewer_id)

    # Set of active reviewers.
    #
    #   { |users.id| }
    active = set()

    # Users that have reviewed changes, per file.
    #
    #   { |files.id|: { |users.id| } }
    active_per_file: Dict[int, Set[int]] = defaultdict(set)

    async with dbaccess.Query[Tuple[int, int]](
        cursor,
        """SELECT DISTINCT reviewfiles.id, reviewuserfiles.uid
             FROM reviewfiles
             JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
            WHERE review={review}
              AND reviewuserfiles.reviewed""",
        review=review,
    ) as result2:
        async for file_id, reviewer_id in result2:
            active.add(reviewer_id)
            active_per_file[file_id].add(reviewer_id)

    # Users that should have the |pending| tag.
    pending: Set[int] = set()
    # Users that should have the |single| tag.
    single: Set[int] = set()
    # Users that should have the |available| tag.
    available: Set[int] = set()
    # Users that should have the |primary| tag.
    primary: Set[int] = set()

    for file_id, file_assigned in assigned_per_file.items():
        if file_id in pending_files:
            pending.update(file_assigned)
        if len(file_assigned) == 1:
            single.update(file_assigned)

        file_assigned_active = file_assigned & active

        # If no assigned reviewer is also an active reviewer, then all assigned
        # reviewers should have the |available| tag.
        if not file_assigned_active:
            available.update(file_assigned)
        # Otherwise, if a single assigned reviewer is also an active reviewer,
        # then that reviewer should have the |primary| tag.
        elif len(file_assigned_active) == 1:
            primary.update(file_assigned_active)

    # Users that should have the |watching| tag.
    watching = set()

    async with dbaccess.Query[int](
        cursor,
        """SELECT uid
             FROM reviewusers
            WHERE review={review}
              AND NOT owner""",
        review=review,
    ) as result3:
        watching.update(set(await result3.scalars()) - (assigned | active))

    # Users tag should have the |unpublished| tag.
    unpublished: Set[int] = set()

    async with dbaccess.Query[int](
        cursor,
        """SELECT DISTINCT reviewfilechanges.uid
             FROM reviewfilechanges
             JOIN reviewfiles ON (reviewfilechanges.file=reviewfiles.id)
            WHERE reviewfiles.review={review}
              AND reviewfilechanges.state='draft'""",
        review=review,
    ) as result3:
        unpublished.update(await result3.scalars())
    async with dbaccess.Query[int](
        cursor,
        """SELECT DISTINCT comments.uid
             FROM comments
             JOIN commentchains ON (comments.chain=commentchains.id)
            WHERE commentchains.review={review}
              AND comments.batch IS NULL""",
        review=review,
    ) as result3:
        unpublished.update(await result3.scalars())
    async with dbaccess.Query[int](
        cursor,
        """SELECT DISTINCT commentchainchanges.uid
             FROM commentchainchanges
             JOIN commentchains ON (
                    commentchainchanges.chain=commentchains.id
                  )
            WHERE commentchains.review={review}
              AND commentchainchanges.state='draft'""",
        review=review,
    ) as result3:
        unpublished.update(await result3.scalars())
    async with dbaccess.Query[int](
        cursor,
        """SELECT DISTINCT commentchainlines.uid
             FROM commentchainlines
             JOIN commentchains ON (
                    commentchainlines.chain=commentchains.id
                  )
            WHERE commentchains.review={review}
              AND commentchainlines.state='draft'""",
        review=review,
    ) as result3:
        unpublished.update(await result3.scalars())

    async with dbaccess.Query[Tuple[str, int]](
        cursor, "SELECT name, id FROM reviewtags"
    ) as result4:
        tag_ids = dict(await result4.all())

    assigned_id = tag_ids["assigned"]
    active_id = tag_ids["active"]
    pending_id = tag_ids["pending"]
    unseen_id = tag_ids["unseen"]
    single_id = tag_ids["single"]
    available_id = tag_ids["available"]
    primary_id = tag_ids["primary"]
    watching_id = tag_ids["watching"]
    unpublished_id = tag_ids["unpublished"]

    relevant_tag_ids = [
        assigned_id,
        active_id,
        pending_id,
        unseen_id,
        single_id,
        available_id,
        primary_id,
        watching_id,
        unpublished_id,
    ]

    await cursor.execute(
        """DELETE
             FROM reviewusertags
            WHERE review={review}
              AND tag=ANY({relevant_tag_ids})""",
        review=review,
        relevant_tag_ids=relevant_tag_ids,
    )

    def values(user_id: int, tag_id: int) -> dbaccess.Parameters:
        return {"review": review, "user_id": user_id, "tag_id": tag_id}

    await cursor.executemany(
        """INSERT
             INTO reviewusertags (review, uid, tag)
           VALUES ({review}, {user_id}, {tag_id})""",
        itertools.chain(
            (values(user_id, assigned_id) for user_id in assigned),
            (values(user_id, active_id) for user_id in active),
            (values(user_id, pending_id) for user_id in pending),
            (values(user_id, unseen_id) for user_id in unseen),
            (values(user_id, single_id) for user_id in single),
            (values(user_id, available_id) for user_id in available),
            (values(user_id, primary_id) for user_id in primary),
            (values(user_id, watching_id) for user_id in watching),
            (values(user_id, unpublished_id) for user_id in unpublished),
        ),
    )


class UpdateReviewTags(Finalizer):
    tables = frozenset({"reviewusertags"})

    def __init__(self, review: api.review.Review) -> None:
        self.__review = review

    def __hash__(self) -> int:
        return hash((UpdateReviewTags, self.__review))

    def should_run_after(self, other: object) -> bool:
        return isinstance(other, FinalizeAssignments)

    async def __call__(
        self, _: TransactionBase, cursor: dbaccess.TransactionCursor
    ) -> None:
        await update_review_tags(self.__review, cursor)
