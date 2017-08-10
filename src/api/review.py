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

class ReviewError(api.APIError):
    """Base exception for all errors related to the Review class."""
    pass

class InvalidReviewId(ReviewError):
    """Raised when an invalid review id is used."""

    def __init__(self, review_id):
        """Constructor"""
        super(InvalidReviewId, self).__init__(
            "Invalid review id: %d" % review_id)

class InvalidReviewBranch(ReviewError):
    """Raised when an invalid review branch is used."""

    def __init__(self, branch):
        """Constructor"""
        super(InvalidReviewBranch, self).__init__(
            "Invalid review branch: %r" % str(branch))

class Review(api.APIObject):
    """Representation of a Critic review"""

    STATE_VALUES = frozenset(["open", "closed", "dropped"])

    @property
    def id(self):
        """The review's unique id"""
        return self._impl.id

    @property
    def state(self):
        """The review's state"""
        return self._impl.state

    @property
    def summary(self):
        """The review's summary"""
        return self._impl.summary

    @property
    def description(self):
        """The review's description, or None"""
        return self._impl.description

    @property
    def repository(self):
        """The review's repository

           The repository is returned as an api.repository.Repository object."""
        return self._impl.getRepository(self.critic)

    @property
    def branch(self):
        """The review's branch

           The branch is returned as an api.branch.Branch object."""
        return self._impl.getBranch(self.critic)

    @property
    def owners(self):
        """The review's owners

           The owners are returned as a set of api.user.User objects."""
        return self._impl.getOwners(self.critic)

    @property
    def reviewers(self):
        """The review's reviewers

           The reviewers are returned as a set of api.user.User objects.

           A user is considered a reviewer if he/she is assigned to review any
           changes (whether those changes have been reviewed already or not,)
           or has reviewed any changes."""
        return self._impl.getReviewers(self.critic)

    @property
    def watchers(self):
        """The review's watchers

           The watchers are returned as a set of api.user.User objects.

           A user is a watcher if he/she is on the list of users that receive
           emails about the review, and is neither an owner nor a reviewer."""
        return self._impl.getWatchers(self.critic)

    @property
    def filters(self):
        """The review's local filters

           The filters are returned as a list of api.filters.ReviewFilter
           objects."""
        return self._impl.getFilters(self.critic)

    @property
    def commits(self):
        """The set of commits that are part of the review

           Note: This set never changes when the review branch is rebased, and
                 commits are never removed from it.  For the set of commits that
                 are actually reachable from the review branch, consult the
                 'commits' attribute on the api.branch.Branch object that is
                 returned by the 'branch' attribute."""
        return self._impl.getCommits(self.critic)

    @property
    def rebases(self):
        """The rebases of the review branch

           The rebases are returned as a list of api.log.rebase.Rebase objects,
           ordered chronologically with the most recent rebase first."""
        return self._impl.getRebases(self)

    @property
    def pending_rebase(self):
        """The pending rebase of the review branch

           The rebase, if it exists, is returned as an api.log.rebase.Rebase
           object. If there isn't a pending rebase, this will be None."""
        return self._impl.getPendingRebase(self)

    @property
    def issues(self):
        """The issues in the review

           The issues are returned as a list of api.comment.Issue objects."""
        return self._impl.getIssues(self)

    @property
    def notes(self):
        """The notes in the review

           The notes are returned as a list of api.comment.Note objects."""
        return self._impl.getNotes(self)

    @property
    def first_partition(self):
        return api.log.partition.create(
            self.critic, self.commits, self.rebases)

def fetch(critic, review_id=None, branch=None):
    """Fetch a Review object with the given id or branch"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert (review_id is None) != (branch is None)
    assert branch is None or isinstance(branch, api.branch.Branch)
    return api.impl.review.fetch(critic, review_id, branch)

def fetchAll(critic, repository=None, state=None):
    """Fetch a Review object with the given id or branch"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert (repository is None or
            isinstance(repository, api.repository.Repository))
    if state is not None:
        if isinstance(state, basestring):
            state = set([state])
        else:
            state = set(state)
        assert not (state - Review.STATE_VALUES)
    return api.impl.review.fetchAll(critic, repository, state)
