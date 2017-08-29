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

class FileChangeError(api.APIError):
    pass

class InvalidFileChangeId(FileChangeError):
    def __init__(self, changeset_id, file_id):
        super(InvalidFileChangeId, self).__init__(
            "Invalid file change id: %d:%d" % (changeset_id, file_id))

class FileChange(api.APIObject):
    """Representation of the changes to a file introduced by a changeset"""

    def __hash__(self):
        return hash((self.changeset, self.file))
    def __eq__(self, other):
        return self.changeset == other.changeset and self.file == other.file

    @property
    def file(self):
        return self._impl.getFile(self.critic)

    @property
    def changeset(self):
        return self._impl.changeset

    @property
    def old_sha1(self):
        return self._impl.old_sha1

    @property
    def old_mode(self):
        return self._impl.old_mode

    @property
    def new_sha1(self):
        return self._impl.new_sha1

    @property
    def new_mode(self):
        return self._impl.new_mode

def fetch(critic, changeset, file):
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(changeset, api.changeset.Changeset)
    assert isinstance(file, api.file.File)
    return api.impl.filechange.fetch(critic, changeset, file)

def fetchAll(critic, changeset):
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(changeset, api.changeset.Changeset)
    return api.impl.filechange.fetchAll(critic, changeset)
