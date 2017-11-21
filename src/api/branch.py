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

class BranchError(api.APIError):
    """Base exception for all errors related to the Branch class."""
    pass

class InvalidBranchId(BranchError):
    """Raised when an invalid branch id is used."""

    def __init__(self, branch_id):
        """Constructor"""
        super(InvalidBranchId, self).__init__(
            "Invalid branch id: %d" % branch_id)

class InvalidBranchName(BranchError):
    """Raised when an invalid branch name is used."""

    def __init__(self, name):
        """Constructor"""
        super(InvalidBranchName, self).__init__(
            "Invalid branch name: %r" % name)

class Branch(api.APIObject):
    """Representation of a Git branch, according to Critic

       Critic extends Git's branch concept by adding a heuristically determined
       base branch, and a derived restricted set of commits that belong to the
       branch by (initially) excluding those reachable from the base branch."""

    @property
    def id(self):
        """The branch's unique id"""
        return self._impl.id

    @property
    def name(self):
        """The branch's name excluding the 'refs/heads/' prefix"""
        return self._impl.name

    @property
    def repository(self):
        """The repository that contains the branch

           The repository is returned as an api.repository.Repository object."""
        return self._impl.getRepository(self.critic)

    @property
    def head(self):
        """The branch's head commit"""
        return self._impl.getHead(self.critic)

    @property
    def commits(self):
        """The commits belonging to the branch

           The return value is an api.commitset.CommitSet object.

           Note: This set of commits is the commits that are actually reachable
                 from the head of the branch.  If the branch is a review branch
                 that has been rebased, this is not the same as the commits that
                 are considered part of the review."""
        return self._impl.getCommits(self.critic)

    @property
    def updates(self):
        """The update log of this branch

           The updates are returned as a list of BranchUpdate objects, ordered
           chronologically with the oldest update first.

           Note: The update log of a branch is cleared if the branch is removed,
                 so for a branch that has been created and deleted multiple
                 times, the log only goes back to the most recent creation of
                 the branch.

           Note: This feature was added in an update of Critic.  In systems
                 installed before that update, existing branches will not have a
                 complete log.  Such branches will have a log that records them
                 as having been created by the system with their then current
                 value, all at the point in time when the system was updated to
                 a version supporting this feature."""
        return api.branchupdate.fetchAll(self)

def fetch(critic, branch_id=None, repository=None, name=None):
    """Fetch a Branch object with the given id or name

       When a name is provided, a repository must also be provided."""
    import api.impl
    assert (branch_id is None) != (name is None)
    assert name is None or repository is not None
    return api.impl.branch.fetch(critic, branch_id, repository, name)

def fetchAll(critic, repository=None):
    """Fetch Branch objects for all branches

       If a repository is provided, restrict the return value to branches in the
       specified repository."""
    import api.impl
    assert (repository is None or
            isinstance(repository, api.repository.Repository))
    return api.impl.branch.fetchAll(critic, repository)
