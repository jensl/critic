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
import api.impl.filters

class Review(object):
    def __init__(self, review_id, repository_id, branch_id, state, summary,
                 description):
        self.id = review_id
        self.__repository_id = repository_id
        self.__branch_id = branch_id
        self.state = state
        self.summary = summary
        self.description = description
        self.__owners_ids = None
        self.__reviewers_ids = None
        self.__watchers_ids = None
        self.__filters = None
        self.__commits = None
        self.__rebases = None

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

    def __fetchReviewers(self, critic):
        if self.__reviewers_ids is None:
            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT DISTINCT uid
                                FROM reviewuserfiles
                                JOIN reviewfiles ON (reviewfiles.id=reviewuserfiles.file)
                               WHERE reviewfiles.review=%s""",
                           (self.id,))
            assigned_reviewers = frozenset(user_id for (user_id,) in cursor)
            cursor.execute("""SELECT DISTINCT uid
                                FROM reviewfilechanges
                                JOIN reviewfiles ON (reviewfiles.id=reviewfilechanges.file)
                               WHERE reviewfiles.review=%s""",
                           (self.id,))
            actual_reviewers = frozenset(user_id for (user_id,) in cursor)
            self.__reviewers_ids = assigned_reviewers | actual_reviewers

    def getReviewers(self, critic):
        self.__fetchReviewers(critic)
        return frozenset(api.user.fetch(critic, user_id=user_id)
                         for user_id in self.__reviewers_ids)

    def __fetchWatchers(self, critic):
        if self.__watchers_ids is None:
            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT uid
                                FROM reviewusers
                               WHERE review=%s""",
                           (self.id,))
            associated_users = frozenset(user_id for (user_id,) in cursor)
            self.__fetchOwners(critic)
            self.__fetchReviewers(critic)
            non_watchers = self.__owners_ids | self.__reviewers_ids
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

    def wrap(self, critic):
        return api.review.Review(critic, self)

def make(critic, args):
    for (review_id, repository_id, branch_id,
         state, summary, description) in args:
        def callback():
            return Review(review_id, repository_id, branch_id,
                          state, summary, description).wrap(critic)
        yield critic._impl.cached(api.review.Review, review_id, callback)

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
    row = cursor.fetchone()
    if not row:
        if review_id is not None:
            raise api.review.InvalidReviewId(review_id)
        else:
            raise api.review.InvalidReviewBranch(branch)
    return next(make(critic, [row]))

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
    return list(make(critic, cursor))
