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
from typing import Optional, Set, Dict, Tuple

logger = logging.getLogger(__name__)

from .finalizeassignments import FinalizeAssignments
from ..base import TransactionBase, Finalizer

from critic import api
from critic import dbaccess


async def update_review_tags(
    review: api.review.Review,
    cursor: dbaccess.TransactionCursor,
    *,
    raised_issues: bool = False,
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

    # Set of active reviewers.
    #
    #   { |users.id| }
    active_published: Set[int] = set()
    active_unpublished: Set[int] = set()

    # Users that have reviewed changes, per file.
    #
    #   { |files.id|: { |users.id| } }
    published_per_file: Dict[int, Set[int]] = defaultdict(set)
    unpublished_per_file: Dict[int, Set[int]] = defaultdict(set)

    async with dbaccess.Query[Tuple[int, int, bool, bool, Optional[bool]]](
        cursor,
        """SELECT reviewuserfiles.uid, reviewfiles.id, reviewfiles.reviewed,
                  reviewuserfiles.reviewed, reviewuserfilechanges.to_reviewed
             FROM reviewuserfiles
             JOIN reviewfiles ON (reviewfiles.id=reviewuserfiles.file)
  LEFT OUTER JOIN reviewuserfilechanges ON (
                    reviewuserfilechanges.file=reviewuserfiles.file AND
                    reviewuserfilechanges.uid=reviewuserfiles.uid AND
                    reviewuserfilechanges.batch IS NULL
                  )
            WHERE reviewfiles.review={review}""",
        review=review,
    ) as result1:
        # is_pending = no-one has reviewed the change
        # has_reviewed = this user has reviewed it (implies `not is_pending`)
        async for (
            reviewer_id,
            file_id,
            is_reviewed,
            is_reviewed_published,
            is_reviewed_unpublished,
        ) in result1:
            assigned.add(reviewer_id)
            assigned_per_file[file_id].add(reviewer_id)
            if not is_reviewed:
                pending_files.add(file_id)
            if is_reviewed_published:
                active_published.add(reviewer_id)
                published_per_file[file_id].add(reviewer_id)
            if is_reviewed_unpublished:
                active_unpublished.add(reviewer_id)
                unpublished_per_file[file_id].add(reviewer_id)

    # Users that should have the |pending| tag.
    pending: Set[int] = set()
    # Users that should have the |single| tag.
    single: Set[int] = set()
    # Users that should have the |available| tag.
    available: Set[int] = set(assigned)
    # Users that should have the |primary| tag.
    primary: Set[int] = set()

    for file_id, file_assigned in assigned_per_file.items():
        if len(file_assigned) == 1:
            # Only a single user is assigned to review this file. Add the
            # |single| tag for this user.
            single.update(file_assigned)

        # Set of assigned users for whom the changes in this file are pending,
        # i.e. who haven't marked the changes as reviewed (published or not).
        file_pending_for_users = (
            file_assigned - published_per_file[file_id] - unpublished_per_file[file_id]
        )

        if file_id in pending_files:
            # File is pending. Add the |pending| tag for any assigned reviewer
            # that hasn't marked the file as reviewed (published or not).
            pending.update(file_pending_for_users)
        else:
            # File is not pending (i.e. it has been marked as reviewed by enough
            # users already). Add the |unseen| tag for any assigned reviewer
            # that hasn't marked it as reviewed (published or not) themselves
            # yet.
            unseen.update(file_pending_for_users)

        # If this file has been reviewed by anyone, subtract all assigned
        # reviewers from the set of users that should have the |available| tag.
        if published_per_file[file_id]:
            available.difference_update(file_assigned)

        # Otherwise, if a single assigned reviewer is also a (published or
        # unpublished) active reviewer, then that reviewer should have the
        # |primary| tag.
        active_per_file = published_per_file[file_id] | unpublished_per_file[file_id]
        for reviewer_id in active_per_file:
            if (file_assigned & active_published).issubset({reviewer_id}):
                primary.add(reviewer_id)

    # The |unseen| tag implies not |pending|, so remove all users that should
    # have the |pending| tag.
    unseen -= pending

    # Users that should have the |active| tag.
    active = active_published | active_unpublished

    # Users that should have the |watching| tag.
    watching: Set[int]

    async with dbaccess.Query[int](
        cursor,
        """SELECT uid
             FROM reviewusers
            WHERE review={review}
              AND NOT owner""",
        review=review,
    ) as result3:
        watching = set(await result3.scalars()) - assigned - active

    # Users tag should have the |unpublished| tag.
    unpublished: Set[int] = set()

    async with dbaccess.Query[int](
        cursor,
        """SELECT DISTINCT reviewuserfilechanges.uid
             FROM reviewuserfilechanges
             JOIN reviewfiles ON (reviewuserfilechanges.file=reviewfiles.id)
            WHERE reviewfiles.review={review}
              AND reviewuserfilechanges.state='draft'""",
        review=review,
    ) as result3:
        unpublished.update(await result3.scalars())
    async with dbaccess.Query[int](
        cursor,
        """SELECT DISTINCT replies.author
             FROM replies
             JOIN comments ON (replies.comment=comments.id)
            WHERE comments.review={review}
              AND replies.batch IS NULL""",
        review=review,
    ) as result3:
        unpublished.update(await result3.scalars())
    async with dbaccess.Query[int](
        cursor,
        """SELECT DISTINCT commentchanges.author
             FROM commentchanges
             JOIN comments ON (
                    commentchanges.comment=comments.id
                  )
            WHERE comments.review={review}
              AND commentchanges.state='draft'""",
        review=review,
    ) as result3:
        unpublished.update(await result3.scalars())
    async with dbaccess.Query[int](
        cursor,
        """SELECT DISTINCT commentlines.author
             FROM commentlines
             JOIN comments ON (
                    commentlines.comment=comments.id
                  )
            WHERE comments.review={review}
              AND commentlines.state='draft'""",
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
    would_be_accepted_id = tag_ids["would_be_accepted"]

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

    if raised_issues:
        relevant_tag_ids.append(would_be_accepted_id)

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

    def __init__(
        self, review: api.review.Review, *, raised_issues: bool = False
    ) -> None:
        self.__review = review
        self.__raised_issues = raised_issues
        super().__init__(self.__review)

    def should_run_after(self, other: object) -> bool:
        return isinstance(other, FinalizeAssignments)

    async def __call__(
        self, _: TransactionBase, cursor: dbaccess.TransactionCursor
    ) -> None:
        await update_review_tags(
            self.__review, cursor, raised_issues=self.__raised_issues
        )
