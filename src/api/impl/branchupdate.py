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
import apiobject

class BranchUpdate(apiobject.APIObject):
    wrapper_class = api.branchupdate.BranchUpdate

    def __init__(self, branchupdate_id, branch_id, updater_id,
                 from_base_id, to_base_id,
                 from_head_id, to_head_id,
                 from_tail_id, to_tail_id,
                 timestamp, output):
        self.id = branchupdate_id
        self.timestamp = timestamp
        self.output = output
        self.__branch_id = branch_id
        self.__updater_id = updater_id
        self.__from_base_id = from_base_id
        self.__to_base_id = to_base_id
        self.__from_head_id = from_head_id
        self.__to_head_id = to_head_id
        self.__from_tail_id = from_tail_id
        self.__to_tail_id = to_tail_id
        self.__associated_commits = None
        self.__disassociated_commits = None
        self.__commits = None

    def getBranch(self, critic):
        return api.branch.fetch(critic, branch_id=self.__branch_id)

    def getUpdater(self, critic):
        if self.__updater_id is None:
            return None
        return api.user.fetch(critic, user_id=self.__updater_id)

    def getFromHead(self, critic):
        if self.__from_head_id is None:
            return None
        branch = self.getBranch(critic)
        return api.commit.fetch(
            branch.repository, commit_id=self.__from_head_id)

    def getToHead(self, critic):
        branch = self.getBranch(critic)
        return api.commit.fetch(branch.repository, commit_id=self.__to_head_id)

    def getAssociatedCommits(self, critic):
        if self.__associated_commits is None:
            repository = self.getBranch(critic).repository
            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT commit
                                FROM branchupdatecommits
                               WHERE branchupdate=%s
                                 AND associated""",
                           (self.id,))
            self.__associated_commits = api.commitset.create(
                critic, (api.commit.fetch(repository, commit_id)
                         for (commit_id,) in cursor))
        return self.__associated_commits

    def getDisassociatedCommits(self, critic):
        if self.__disassociated_commits is None:
            repository = self.getBranch(critic).repository
            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT commit
                                FROM branchupdatecommits
                               WHERE branchupdate=%s
                                 AND NOT associated""",
                           (self.id,))
            self.__disassociated_commits = api.commitset.create(
                critic, (api.commit.fetch(repository, commit_id)
                         for (commit_id,) in cursor))
        return self.__disassociated_commits

@BranchUpdate.cached(api.branchupdate.InvalidBranchUpdateId)
def fetch(critic, branchupdate_id):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT id, branch, updater,
                             from_base, to_base,
                             from_head, to_head,
                             from_tail, to_tail,
                             updated_at, output
                        FROM branchupdates
                       WHERE id=%s""",
                   (branchupdate_id,))
    return BranchUpdate.make(critic, cursor)

def fetchAll(branch):
    cursor = branch.critic.getDatabaseCursor()
    cursor.execute("""SELECT id, branch, updater,
                             from_base, to_base,
                             from_head, to_head,
                             from_tail, to_tail,
                             updated_at, output
                        FROM branchupdates
                       WHERE branch=%s
                    ORDER BY id ASC""",
                   (branch.id,))
    return list(BranchUpdate.make(branch.critic, cursor))
