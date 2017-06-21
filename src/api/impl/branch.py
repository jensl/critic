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

class Branch(apiobject.APIObject):
    wrapper_class = api.branch.Branch

    def __init__(self, branch_id, name, repository_id, head_id):
        self.id = branch_id
        self.name = name
        self.__repository_id = repository_id
        self.__head_id = head_id
        self.__head = None
        self.__commits = None

    def getRepository(self, critic):
        return api.repository.fetch(critic, repository_id=self.__repository_id)

    def getHead(self, critic):
        if self.__head is None:
            self.__head = api.commit.fetch(
                self.getRepository(critic), commit_id=self.__head_id)
        return self.__head

    def getCommits(self, critic):
        if self.__commits is None:
            repository = self.getRepository(critic)
            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT commit
                                FROM branchcommits
                               WHERE branch=%s""",
                           (self.id,))
            self.__commits = api.commitset.create(
                critic, (api.commit.fetch(repository, commit_id)
                         for (commit_id,) in cursor))
        return self.__commits

@Branch.cached()
def fetch(critic, branch_id, repository, name):
    cursor = critic.getDatabaseCursor()
    if branch_id is not None:
        cursor.execute("""SELECT id, name, repository, head
                            FROM branches
                           WHERE id=%s""",
                       (branch_id,))
    else:
        cursor.execute("""SELECT id, name, repository, head
                            FROM branches
                           WHERE repository=%s
                             AND name=%s""",
                       (repository.id, name,))
    try:
        return next(Branch.make(critic, cursor))
    except StopIteration:
        if branch_id is not None:
            raise api.branch.InvalidBranchId(branch_id)
        else:
            raise api.branch.InvalidBranchName(name)

def fetchAll(critic, repository):
    cursor = critic.getDatabaseCursor()
    if repository is not None:
        cursor.execute("""SELECT id, name, repository, head
                            FROM branches
                           WHERE repository=%s
                        ORDER BY name""",
                       (repository.id,))
    else:
        cursor.execute("""SELECT id, name, repository, head
                            FROM branches
                        ORDER BY name""")
    return list(Branch.make(critic, cursor))
