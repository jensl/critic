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

import api
import apiobject
import api.impl.filters

import auth

class Review(apiobject.APIObject):
    wrapper_class = api.review.Review

    def __init__(self, review_id, repository_id, branch_id, state, summary,
                 description):
        self.id = review_id
        self.__repository_id = repository_id
        self.__branch_id = branch_id
        self.state = state
        self.summary = summary
        self.description = description
        self.__owners_ids = None
        self.__assigned_reviewers_ids = None
        self.__active_reviewers_ids = None
        self.__watchers_ids = None
        self.__filters = None
        self.__commits = None
        self.__rebases = None
        self.__issues = None
        self.__notes = None
        self.__open_issues = None
        self.__total_progress = None
        self.__progress_per_commit = None

    def getRepository(self, critic):
        return api.repository.fetch(critic, repository_id=self.__repository_id)

    def getBranch(self, critic):
        return api.branch.fetch(critic, branch_id=self.__branch_id)

    def __fetchOwners(self, critic):
        if self.__owners_ids is None:
            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT uid
                                FROM reviewusers
                               WHERE review=%s
                                 AND owner""",
                           (self.id,))
            self.__owners_ids = frozenset(user_id for (user_id,) in cursor)

    def getOwners(self, critic):
        self.__fetchOwners(critic)
        return frozenset(api.user.fetch(critic, user_id=user_id)
                         for user_id in self.__owners_ids)

    def __fetchAssignedReviewers(self, critic):
        if self.__assigned_reviewers_ids is None:
            cursor = critic.getDatabaseCursor()
            cursor.execute(
                """SELECT DISTINCT uid
                     FROM reviewuserfiles
                     JOIN reviewfiles ON (reviewfiles.id=reviewuserfiles.file)
                    WHERE reviewfiles.review=%s""",
                (self.id,))
            self.__assigned_reviewers_ids = frozenset(
                user_id for (user_id,) in cursor)

    def getAssignedReviewers(self, critic):
        self.__fetchAssignedReviewers(critic)
        return frozenset(api.user.fetchMany(
            critic, user_ids=self.__assigned_reviewers_ids))

    def __fetchActiveReviewers(self, critic):
        if self.__active_reviewers_ids is None:
            cursor = critic.getDatabaseCursor()
            cursor.execute(
                """SELECT DISTINCT uid
                     FROM reviewfilechanges
                     JOIN reviewfiles ON (reviewfiles.id=reviewfilechanges.file)
                    WHERE reviewfiles.review=%s""",
                (self.id,))
            self.__active_reviewers_ids = frozenset(
                user_id for (user_id,) in cursor)

    def getActiveReviewers(self, critic):
        self.__fetchActiveReviewers(critic)
        return frozenset(api.user.fetchMany(
            critic, user_ids=self.__active_reviewers_ids))

    def __fetchWatchers(self, critic):
        if self.__watchers_ids is None:
            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT uid
                                FROM reviewusers
                               WHERE review=%s""",
                           (self.id,))
            associated_users = frozenset(user_id for (user_id,) in cursor)
            self.__fetchOwners(critic)
            self.__fetchAssignedReviewers(critic)
            self.__fetchActiveReviewers(critic)
            non_watchers = self.__owners_ids | self.__assigned_reviewers_ids | \
                           self.__active_reviewers_ids
            self.__watchers_ids = associated_users - non_watchers

    def getWatchers(self, critic):
        self.__fetchWatchers(critic)
        return frozenset(api.user.fetch(critic, user_id=user_id)
                         for user_id in self.__watchers_ids)

    def getFilters(self, critic):
        if self.__filters is None:
            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT uid, type, path, id, review, creator
                                FROM reviewfilters
                               WHERE review=%s""",
                           (self.id,))
            impls = [api.impl.filters.ReviewFilter(*row) for row in cursor]
            self.__filters = [api.filters.ReviewFilter(critic, impl)
                              for impl in impls]
        return self.__filters

    def getCommits(self, critic):
        if self.__commits is None:
            cursor = critic.getDatabaseCursor()
            # Direct changesets: no merges, no rebase changes.
            cursor.execute(
                """SELECT DISTINCT commits.id, commits.sha1
                     FROM commits
                     JOIN changesets ON (changesets.child=commits.id)
                     JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                    WHERE reviewchangesets.review=%s
                      AND changesets.type='direct'""",
                (self.id,))
            commit_ids_sha1s = set(cursor)
            # Merge changesets, excluding those added by move rebases.
            cursor.execute(
                """SELECT DISTINCT commits.id, commits.sha1
                     FROM commits
                     JOIN changesets ON (changesets.child=commits.id)
                     JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
          LEFT OUTER JOIN reviewrebases ON (reviewrebases.review=%s
                                        AND reviewrebases.equivalent_merge=commits.id)
                    WHERE reviewchangesets.review=%s
                      AND changesets.type='merge'
                      AND reviewrebases.id IS NULL""",
                (self.id, self.id))
            commit_ids_sha1s.update(cursor)
            repository = self.getRepository(critic)
            commits = [api.commit.fetch(repository, commit_id, sha1)
                       for commit_id, sha1 in commit_ids_sha1s]
            self.__commits = api.commitset.create(critic, commits)
        return self.__commits

    def getRebases(self, wrapper):
        return api.log.rebase.fetchAll(wrapper.critic, wrapper)

    def getPendingRebase(self, wrapper):
        rebases = api.log.rebase.fetchAll(wrapper.critic, wrapper, pending=True)
        if len(rebases) == 1:
            return rebases[0]
        else:
            return None

    def getIssues(self, wrapper):
        if self.__issues is None:
            self.__issues = api.comment.fetchAll(
                wrapper.critic, review=wrapper, comment_type="issue")
        return self.__issues

    def getOpenIssues(self, wrapper):
        if self.__open_issues is None:
            self.__open_issues = [issue
                                  for issue
                                  in self.getIssues(wrapper)
                                  if issue.state == "open"]
        return self.__open_issues

    def getNotes(self, wrapper):
        if self.__notes is None:
            self.__notes = api.comment.fetchAll(
                wrapper.critic, review=wrapper, comment_type="note")
        return self.__notes

    def isReviewableCommit(self, critic, commit):
        cursor = critic.getDatabaseCursor()
        cursor.execute(
            """SELECT 1
                 FROM reviewchangesets
                 JOIN changesets ON (changesets.id=reviewchangesets.changeset)
                WHERE reviewchangesets.review=%s
                  AND changesets.child=%s""",
            (self.id, commit.id))
        return bool(cursor.fetchone())

    def getTotalProgress(self, critic):
        if self.__total_progress is None:
            cursor = critic.getDatabaseCursor()
            cursor.execute(
                """SELECT state, sum(inserted+deleted)
                     FROM reviewfiles
                    WHERE review=%s
                 GROUP BY state""",
                (self.id,))

            reviewed = 0
            pending = 0
            for state, modifications in cursor:
                if modifications == 0: # binary file change
                    actual_modifications = 1
                else:
                    actual_modifications = modifications
                if state == "reviewed":
                    reviewed = actual_modifications
                elif state == "pending":
                    pending = actual_modifications

            total = reviewed + pending
            if reviewed == 0:
                self.__total_progress = 0
            elif pending == 0:
                self.__total_progress = 1
            else:
                self.__total_progress = reviewed / float(total)
        return self.__total_progress

    def getProgressPerCommit(self, critic):
        if self.__progress_per_commit is None:
            cursor = critic.getDatabaseCursor()
            cursor.execute(
                """SELECT changesets.child, SUM(deleted + inserted)
                     FROM reviewfiles
                     JOIN changesets ON changesets.id=reviewfiles.changeset
                    WHERE reviewfiles.review=%s
                 GROUP BY changesets.child""",
                (self.id,))

            total_changes_dict = {}
            for commit_id, changes in cursor:
                total_changes_dict[commit_id] = changes

            cursor.execute(
                """SELECT changesets.child, SUM(deleted + inserted)
                     FROM reviewfiles
                     JOIN changesets ON changesets.id=reviewfiles.changeset
                    WHERE reviewfiles.review=%s AND state='reviewed'
                 GROUP BY changesets.child""",
                (self.id,))

            reviewed_changes_dict = {}
            for commit_id, changes in cursor:
                reviewed_changes_dict[commit_id] = changes

            commit_change_counts = []
            for commit_id, total_changes in total_changes_dict.iteritems():
                reviewed_changes = reviewed_changes_dict.get(commit_id, 0)

                commit_change_counts.append(api.review.CommitChangeCount(
                    commit_id, total_changes, reviewed_changes))

            self.__progress_per_commit = commit_change_counts
        return self.__progress_per_commit

    def getPendingUpdate(self, critic):
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT id
                            FROM branchupdates
                 LEFT OUTER JOIN reviewupdates ON (branchupdate=id)
                           WHERE branch=%s
                             AND review IS NULL""",
                       (self.__branch_id,))
        row = cursor.fetchone()
        if row:
            branchupdate_id, = row
            return api.branchupdate.fetch(critic, branchupdate_id)
        return None

    @classmethod
    def create(Review, critic, *args):
        review = Review(*args).wrap(critic)
        # Access the repository object to trigger an access control check.
        review.repository
        return review

@Review.cached()
def fetch(critic, review_id, branch):
    cursor = critic.getDatabaseCursor()
    if review_id is not None:
        cursor.execute("""SELECT reviews.id, branches.repository, branches.id,
                                 state, summary, description
                            FROM reviews
                            JOIN branches ON (branches.id=reviews.branch)
                           WHERE reviews.id=%s""",
                       (review_id,))
    else:
        cursor.execute("""SELECT reviews.id, branches.repository, branches.id,
                                 state, summary, description
                            FROM reviews
                            JOIN branches ON (branches.id=reviews.branch)
                           WHERE branches.id=%s""",
                       (int(branch),))
    try:
        return next(Review.make(critic, cursor))
    except StopIteration:
        if review_id is not None:
            raise api.review.InvalidReviewId(review_id)
        else:
            raise api.review.InvalidReviewBranch(branch)

def fetchMany(critic, review_ids):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT reviews.id, branches.repository, branches.id,
                             state, summary, description
                        FROM reviews
                        JOIN branches ON (branches.id=reviews.branch)
                       WHERE reviews.id=ANY (%s)""",
                   (review_ids,))

    reviews_by_id = {review.id: review for review in Review.make(critic, cursor)}

    return [reviews_by_id[review_id] for review_id in review_ids]

def fetchAll(critic, repository, state):
    cursor = critic.getDatabaseCursor()
    conditions = ["TRUE"]
    values = []
    if repository is not None:
        conditions.append("branches.repository=%s")
        values.append(repository.id)
    if state is not None:
        conditions.append("reviews.state IN (%s)"
                          % ", ".join(["%s"] * len(state)))
        values.extend(state)
    cursor.execute("""SELECT reviews.id, branches.repository, branches.id,
                             state, summary, description
                        FROM reviews
                        JOIN branches ON (branches.id=reviews.branch)
                       WHERE """ + " AND ".join(conditions) + """
                    ORDER BY reviews.id""",
                   values)
    return list(Review.make(
        critic, cursor, ignored_errors=(auth.AccessDenied,)))
