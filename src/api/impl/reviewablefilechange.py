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

import api
from . import apiobject

class ReviewableFileChange(apiobject.APIObject):
    wrapper_class = api.reviewablefilechange.ReviewableFileChange

    def __init__(self, filechange_id, review_id, changeset_id, file_id,
                 deleted_lines, inserted_lines, reviewed_by_id):
        self.id = filechange_id
        self.__review_id = review_id
        self.__changeset_id = changeset_id
        self.__file_id = file_id
        self.inserted_lines = inserted_lines
        self.deleted_lines = deleted_lines
        self.is_reviewed = reviewed_by_id is not None
        self.__reviewed_by_id = reviewed_by_id
        self.__assigned_reviewers = None
        self.__draft_changes = None
        self.__draft_changes_fetched = False

    def getReview(self, critic):
        return api.review.fetch(critic, self.__review_id)

    def getChangeset(self, critic):
        review = self.getReview(critic)
        return api.changeset.fetch(
            critic, review.repository, self.__changeset_id)

    def getFile(self, critic):
        return api.file.fetch(critic, self.__file_id)

    def getReviewedBy(self, critic):
        if self.__reviewed_by_id is None:
            return None
        return api.user.fetch(critic, self.__reviewed_by_id)

    def getAssignedReviewers(self, critic):
        if self.__assigned_reviewers is None:
            cached_objects = ReviewableFileChange.allCached(critic)
            assert self.id in cached_objects

            # Filter out those cached objects (including this) whose assigned
            # reviewers hasn't been fetched yet.
            need_fetch = set()
            for filechange in cached_objects.values():
                if filechange._impl.__assigned_reviewers is None:
                    filechange._impl.__assigned_reviewers = set()
                    need_fetch.add(filechange.id)
            assert self.id in need_fetch

            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT file, uid
                                FROM reviewuserfiles
                               WHERE file=ANY (%s)""",
                           (list(need_fetch),))
            for filechange_id, reviewer_id in cursor:
                filechange = cached_objects[filechange_id]
                filechange._impl.__assigned_reviewers.add(
                    api.user.fetch(critic, reviewer_id))

            for filechange_id in need_fetch:
                filechange = cached_objects[filechange_id]
                filechange._impl.__assigned_reviewers = frozenset(
                    filechange._impl.__assigned_reviewers)

        return self.__assigned_reviewers

    def getDraftChanges(self, critic):
        if not self.__draft_changes_fetched:
            cached_objects = ReviewableFileChange.allCached(critic)
            assert self.id in cached_objects

            # Filter out those cached objects (including this) whose draft
            # changes hasn't been fetched yet.
            need_fetch = set()
            for filechange in cached_objects.values():
                if not filechange._impl.__draft_changes_fetched:
                    need_fetch.add(filechange.id)
            assert self.id in need_fetch

            cursor = critic.getDatabaseCursor()
            cursor.execute(
                """SELECT file, from_state='reviewed', to_state='reviewed'
                     FROM reviewfilechanges
                    WHERE uid=%s
                      AND state='draft'
                      AND file=ANY (%s)""",
                (critic.effective_user.id, list(need_fetch)))

            draft_changes = {
                filechange_id: (from_is_reviewed, to_is_reviewed)
                for filechange_id, from_is_reviewed, to_is_reviewed in cursor
            }

            for filechange_id in need_fetch:
                filechange = cached_objects[filechange_id]
                filechange._impl.__draft_changes_fetched = True
                if filechange_id not in draft_changes:
                    # No unpublished changes in the database.
                    continue
                from_is_reviewed, to_is_reviewed = draft_changes[filechange_id]
                if filechange.is_reviewed != from_is_reviewed:
                    # The unpublished change has been made redundant, typically
                    # by another user making the same change.
                    continue
                new_reviewed_by = (critic.actual_user
                                   if to_is_reviewed else None)
                filechange._impl.__draft_changes = \
                    api.reviewablefilechange.ReviewableFileChange.DraftChanges(
                        critic.actual_user, new_reviewed_by)

        return self.__draft_changes

    @staticmethod
    def refresh(critic, tables, cached_filechanges):
        if not tables.intersection(("reviewfiles", "reviewfilechanges",
                                    "reviewuserfiles")):
            return

        ReviewableFileChange.updateAll(
            critic,
            """SELECT id, review, changeset, file, deleted, inserted,
                      reviewer
                 FROM reviewfiles
                WHERE id=ANY (%s)""",
            cached_filechanges)

@ReviewableFileChange.cached(
    api.reviewablefilechange.InvalidReviewableFileChangeId)
def fetch(critic, filechange_id):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT id, review, changeset, file, deleted, inserted,
                             reviewer
                        FROM reviewfiles
                       WHERE id=%s""",
                   (filechange_id,))
    return ReviewableFileChange.make(critic, cursor)

@ReviewableFileChange.cachedMany(
    api.reviewablefilechange.InvalidReviewableFileChangeIds)
def fetchMany(critic, filechange_ids):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT id, review, changeset, file, deleted, inserted,
                             reviewer
                        FROM reviewfiles
                       WHERE id=ANY (%s)""",
                   (filechange_ids,))
    return ReviewableFileChange.make(critic, cursor)

def fetchAll(critic, review, changeset, file, assignee, is_reviewed):
    cursor = critic.getDatabaseCursor()
    tables = ["reviewfiles"]
    conditions = ["reviewfiles.review=%s"]
    values = [review.id]
    if changeset:
        # Check if the changeset is a "squash" of the changes in multiple
        # commits. If so, return the reviewable file changes from each of the
        # commits.
        contributing_commits = changeset.contributing_commits
        if contributing_commits is None:
            raise api.reviewablefilechange.InvalidChangeset(changeset)
        if len(contributing_commits) > 1:
            result = []
            try:
                for commit in contributing_commits:
                    # Note: Checking that it is a reviewable commit here is sort
                    # of redundant; we could just call fetchAll() recursively,
                    # and it would raise an InvalidChangeset if it is not. The
                    # problem is that if it is not a reviewable commit, there
                    # may not be a changeset prepared for it, which would make
                    # this asynchronous. As long as we only deal with reviewable
                    # commits, the api.changeset.fetch() call is guaranteed to
                    # succeed synchronously.
                    if not review.isReviewableCommit(commit):
                        raise api.reviewablefilechange.InvalidChangeset(
                            changeset)
                    commit_changeset = api.changeset.fetch(
                        critic, review.repository, single_commit=commit)
                    result.extend(fetchAll(critic, review, commit_changeset,
                                           file, assignee, is_reviewed))
            except api.reviewablefilechange.InvalidChangeset:
                raise api.reviewablefilechange.InvalidChangeset(changeset)
            return sorted(result, key=lambda change: change.id)
        elif not review.isReviewableCommit(next(iter(contributing_commits))):
            raise api.reviewablefilechange.InvalidChangeset(changeset)
        conditions.append("reviewfiles.changeset=%s")
        values.append(changeset.id)
    if file:
        conditions.append("reviewfiles.file=%s")
        values.append(file.id)
    if assignee:
        tables.append("JOIN reviewuserfiles "
                      " ON (reviewuserfiles.file=reviewfiles.id)")
        conditions.append("reviewuserfiles.uid=%s")
        values.append(assignee.id)
    if is_reviewed is not None:
        if assignee:
            # If the specified assignee has a draft change to the state, use
            # that changed state instead of the actual state when filtering.
            tables.append("LEFT OUTER JOIN reviewfilechanges "
                          " ON (reviewfilechanges.file=reviewfiles.id"
                          " AND reviewfilechanges.uid=reviewuserfiles.uid"
                          " AND reviewfilechanges.state='draft')")
            conditions.append("COALESCE(reviewfilechanges.to_state,"
                              "         reviewfiles.state)=%s")
        else:
            conditions.append("reviewfiles.state=%s")
        values.append("reviewed" if is_reviewed else "pending")
    cursor.execute("""SELECT reviewfiles.id, reviewfiles.review,
                             reviewfiles.changeset, reviewfiles.file,
                             reviewfiles.deleted, reviewfiles.inserted,
                             reviewfiles.reviewer
                        FROM {}
                       WHERE {}
                    ORDER BY id""".format(
                        " ".join(tables),
                        " AND ".join(conditions)),
                   values)
    return list(ReviewableFileChange.make(critic, cursor))
