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

class ChangesetError(api.APIError):
    pass

class ChangesetBackgroundServiceError(ChangesetError):
    pass

class InvalidChangesetId(ChangesetError):
    pass

class NotImplementedError(ChangesetError):
    pass

class ChangesetDelayed(api.ResultDelayedError):
    pass

class AutomaticChangesetEmpty(ChangesetError):
    """Raised when fetching an automatic changeset, and no changes were found"""
    pass

class Changeset(api.APIObject):
    """Representation of a diff"""

    AUTOMATIC_MODES = frozenset([
        # All changes in the review.
        "everything",
        # All changes in the review that are either assigned to the current user
        # or that matches one of the current user's watcher filters.
        "relevant",
        # All changes in the review that are assigned to the current user.
        "reviewable",
        # All pending changes in the review that are assigned to the current
        # user.
        "pending",
    ])

    def __str__(self):
        return str(self._impl.id) + " (" + str(self._impl.type) + ")"

    @property
    def id(self):
        return self._impl.id

    @property
    def repository(self):
        """The repository containing the compared commits"""
        return self._impl.repository

    @property
    def type(self):
        return self._impl.type

    @property
    def from_commit(self):
        return self._impl.getFromCommit()

    @property
    def to_commit(self):
        return self._impl.getToCommit()

    @property
    def files(self):
        return api.filechange.fetchAll(self.critic, self)

    @property
    def contributing_commits(self):
        return self._impl.getContributingCommits(self.critic)

def fetch(critic, repository, changeset_id=None, from_commit=None,
          to_commit=None, single_commit=None, review=None, automatic=None):
    """Fetch a single changeset from the given repository"""

    import api.impl
    if changeset_id is not None:
        assert (from_commit is None and to_commit is None and single_commit is None)
    else:
        if automatic is not None:
            assert isinstance(review, api.review.Review)
            assert automatic in Changeset.AUTOMATIC_MODES
            assert (from_commit is None and to_commit is None and
                    single_commit is None)
        else:
            assert (from_commit is None) == (to_commit is None)
            assert (single_commit is None) != (from_commit is None)
            assert (from_commit is None or
                    isinstance(from_commit, api.commit.Commit))
            assert (to_commit is None or
                    isinstance(to_commit, api.commit.Commit))
            if single_commit is not None:
                assert isinstance(single_commit, api.commit.Commit)
                assert len(single_commit.parents) <= 1
            if from_commit is not None and to_commit is not None:
                assert from_commit.id != to_commit.id
    return api.impl.changeset.fetch(
        critic, repository, changeset_id, from_commit, to_commit, single_commit,
        review, automatic)
