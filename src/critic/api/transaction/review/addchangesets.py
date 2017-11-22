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
import collections
from typing import Any, Collection, Optional, Set, List, Dict, Tuple


logger = logging.getLogger(__name__)

from .updatereviewtags import UpdateReviewTags
from .. import Transaction, Query, InsertMany
from critic import api
from critic import dbaccess
from critic import reviewing


async def add_changesets(
    transaction: Transaction,
    review: api.review.Review,
    changesets: Collection[api.changeset.Changeset],
    branchupdate: Optional[api.branchupdate.BranchUpdate],
    commits: Optional[api.commitset.CommitSet],
) -> None:
    reviewchangesets_values: List[dbaccess.Parameters] = []
    reviewfiles_values: List[dbaccess.Parameters] = []

    if commits is None:
        assert branchupdate
        commits = await branchupdate.associated_commits

    changed_files: Set[api.file.File] = set()
    scope_filters: List[
        Tuple[reviewing.filters.Path, bool, api.reviewscope.ReviewScope]
    ] = []

    for scope_filter in await api.reviewscopefilter.fetchAll(
        transaction.critic, repository=await review.repository
    ):
        scope_filters.append(
            (
                reviewing.filters.Path(scope_filter.path),
                scope_filter.included,
                await scope_filter.scope,
            )
        )
    scope_filters.sort()
    logger.debug(f"{scope_filters=}")

    for changeset in changesets:
        reviewchangesets_values.append(
            dict(review=review, branchupdate=branchupdate, changeset=changeset)
        )
        filechanges = await changeset.files
        # We shouldn't be called with incomplete changesets.
        assert filechanges is not None
        changed_files.update(filechange.file for filechange in filechanges)
        for filediff in await api.filediff.fetchAll(changeset):
            file = filediff.filechange.file
            row_data: Dict[str, Any] = dict(
                review=review,
                changeset=changeset,
                file=file,
                scope=None,
                deleted=(await filediff.old_count) or 0,
                inserted=(await filediff.new_count) or 0,
            )
            reviewfiles_values.append(row_data.copy())
            scopes = set()
            for path, included, scope in scope_filters:
                if path.match(file.path):
                    logger.debug(f"{path.regexp=} matched {file.path=}")
                    if included:
                        scopes.add(scope)
                    elif scope in scopes:
                        scopes.remove(scope)
                else:
                    logger.debug(f"{path.regexp=} mismatched {file.path=}")
            for scope in scopes:
                row_data["scope"] = scope
                reviewfiles_values.append(row_data.copy())

    logger.debug(f"{reviewfiles_values=}")

    transaction.items.append(
        InsertMany(
            "reviewchangesets",
            ["review", "branchupdate", "changeset"],
            reviewchangesets_values,
        )
    )
    transaction.items.append(
        InsertMany(
            "reviewfiles",
            ["review", "changeset", "file", "scope", "deleted", "inserted"],
            reviewfiles_values,
        )
    )

    from ....reviewing.assignments import calculateAssignments

    assignments = await calculateAssignments(review, changesets=changesets)

    logger.debug("assignments: %r", assignments)

    if assignments:
        associated_users = (
            (await review.assigned_reviewers)
            | (await review.active_reviewers)
            | (await review.watchers)
        )
        new_users = set(assignments.per_user.keys()) - associated_users

        if new_users:
            transaction.tables.add("reviewusers")
            transaction.items.append(
                InsertMany(
                    "reviewusers",
                    ["review", "uid"],
                    [dict(review=review, uid=user) for user in new_users],
                )
            )

        default_reviewuserfiles_values = [
            dict(
                review=review,
                user=assignment.user,
                changeset=assignment.changeset,
                file=assignment.file,
            )
            for assignment in assignments
            if assignment.scope is None
        ]
        scoped_reviewuserfiles_values = [
            dict(
                review=review,
                user=assignment.user,
                changeset=assignment.changeset,
                file=assignment.file,
                scope=assignment.scope,
            )
            for assignment in assignments
            if assignment.scope
        ]

        transaction.tables.add("reviewuserfiles")
        transaction.items.append(
            Query(
                """INSERT
                     INTO reviewuserfiles (file, uid)
                   SELECT id, {user}
                     FROM reviewfiles
                    WHERE review={review}
                      AND changeset={changeset}
                      AND file={file}
                      AND scope IS NULL""",
                *default_reviewuserfiles_values,
            )
        )
        transaction.items.append(
            Query(
                """INSERT
                     INTO reviewuserfiles (file, uid)
                   SELECT id, {user}
                     FROM reviewfiles
                    WHERE review={review}
                      AND changeset={changeset}
                      AND file={file}
                      AND scope={scope}""",
                *scoped_reviewuserfiles_values,
            )
        )

    if branchupdate:
        critic = transaction.critic
        from_head = await branchupdate.from_head
        # We expect to be called for branch updates, not the initial branch
        # creation.
        assert from_head is not None
        comments = await api.comment.fetchAll(
            critic, review=review, commit=from_head, files=changed_files
        )
        commentchains_values: List[dbaccess.Parameters] = []
        commentchainlines_values: List[dbaccess.Parameters] = []

        logger.debug("from_head: %r", from_head)
        logger.debug("comments: %r", comments)

        existing_locations: Dict[
            int, Dict[str, Tuple[int, int]]
        ] = collections.defaultdict(dict)

        async with critic.query(
            """SELECT chain, sha1, first_line, last_line
                 FROM commentchainlines
                WHERE {chain=comment_ids:array}""",
            comment_ids=[comment.id for comment in comments],
        ) as result:
            async for comment_id, sha1, first_line, last_line in result:
                existing_locations[comment_id][sha1] = (first_line, last_line)

        for comment in comments:
            original_location = await comment.location
            # We fetched comments in the changed files, so all files will have
            # file-version locations.
            assert original_location and original_location.type == "file-version"
            location = await original_location.as_file_version.translateTo(
                commit=from_head
            )
            propagation_result = await reviewing.comment.propagate.propagate_in_new_commits(
                critic, location, existing_locations[comment.id], commits
            )

            commentchainlines_values.extend(
                dict(
                    chain=comment,
                    state="draft" if comment.is_draft else "current",
                    sha1=location.sha1,
                    first_line=location.first_line + 1,
                    last_line=location.last_line + 1,
                )
                for location in propagation_result.locations
                if location.is_new
            )

            if propagation_result.addressed_by:
                commentchains_values.append(
                    dict(
                        comment=comment,
                        addressed_by=propagation_result.addressed_by,
                        branchupdate=branchupdate,
                    )
                )

        if commentchains_values:
            logger.debug("address comments: %r", commentchains_values)

            transaction.tables.add("commentchains")
            transaction.items.append(
                Query(
                    """UPDATE commentchains
                          SET state='addressed',
                              addressed_by={addressed_by},
                              addressed_by_update={branchupdate}
                        WHERE id={comment}""",
                    *commentchains_values,
                )
            )

        if commentchainlines_values:
            transaction.tables.add("commentchainlines")
            transaction.items.append(
                InsertMany(
                    "commentchainlines",
                    ["chain", "state", "sha1", "first_line", "last_line"],
                    commentchainlines_values,
                )
            )

    transaction.finalizers.add(UpdateReviewTags(review))
