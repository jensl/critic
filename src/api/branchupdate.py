# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

class BranchUpdateError(api.APIError):
    """Base exception for all errors related to the BranchUpdate class"""
    pass

class InvalidBranchUpdateId(BranchUpdateError):
    """Raised when an invalid branch update id is used"""

    def __init__(self, branchupdate_id):
        """Constructor"""
        super(InvalidBranchUpdateId, self).__init__(
            "Invalid branch update id: %d" % branchupdate_id)

class BranchUpdate(api.APIObject):
    """Representation of a single update of a Git branch"""

    @property
    def id(self):
        """The branch update's unique id"""
        return self._impl.id

    @property
    def branch(self):
        """The branch that was updated"""
        return self._impl.getBranch(self.critic)

    @property
    def updater(self):
        """The user that performed the update

           None if this update was performed by the system."""
        return self._impl.getUpdater(self.critic)

    @property
    def from_head(self):
        """The old value of the branch's |head| property

           None if this update represents the branch being created."""
        return self._impl.getFromHead(self.critic)

    @property
    def to_head(self):
        """The new value of the branch's |head| property"""
        return self._impl.getToHead(self.critic)

    @property
    def associated_commits(self):
        """The commits that were associated with the branch as of this update

           This does not include any commit that was already associated with
           the branch before the update.

           The return value is an api.commitset.CommitSet object."""
        return self._impl.getAssociatedCommits(self.critic)

    @property
    def disassociated_commits(self):
        """The commits that were disassociated with the branch as of this update

           The return value is an api.commitset.CommitSet object."""
        return self._impl.getDisassociatedCommits(self.critic)

    @property
    def timestamp(self):
        """The moment in time when the update was performed

           The timestamp is returned as a datetime.datetime object."""
        return self._impl.timestamp

    @property
    def output(self):
        """The Git hook output of the update"""
        return self._impl.output

def fetch(critic, branchupdate_id):
    """Fetch a BranchUpdate object with the given id"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    return api.impl.branchupdate.fetch(critic, int(branchupdate_id))

def fetchAll(branch):
    """Fetch all updates of the given branch

       The updates are returned as a list of BranchUpdate objects, ordered
       chronologically with the oldest update first."""
    import api.impl
    assert isinstance(branch, api.branch.Branch)
    return api.impl.branchupdate.fetchAll(branch)
