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
import api.impl
from . import apiobject

class FileChange(apiobject.APIObject):
    wrapper_class = api.filechange.FileChange

    def __init__(self, changeset,
                 file_id, old_sha1, old_mode, new_sha1, new_mode):
        self.changeset = changeset
        self.__file_id = file_id
        self.old_sha1 = old_sha1 if old_sha1 != "0" * 40 else None
        self.old_mode = old_mode
        self.new_sha1 = new_sha1 if new_sha1 != "0" * 40 else None
        self.new_mode = new_mode

    def getFile(self, critic):
        return api.file.fetch(critic, self.__file_id)

@FileChange.cached(api.filechange.InvalidFileChangeId,
                   cache_key=lambda (changeset, file): (changeset.id, file.id))
def fetch(critic, changeset, file):
    cursor = critic.getDatabaseCursor()
    cursor.execute(
        """SELECT file, old_sha1, old_mode, new_sha1, new_mode
             FROM fileversions
            WHERE changeset=%s
              AND file=%s""",
        (changeset.id, file.id,))
    def cache_key(args):
        return args[0].id, args[1]
    return FileChange.make(critic, ((changeset,) + row for row in cursor),
                           cache_key=cache_key)

def fetchAll(critic, changeset):
    cursor = critic.getDatabaseCursor()
    cursor.execute(
        """SELECT file, old_sha1, old_mode, new_sha1, new_mode
             FROM fileversions
             JOIN files ON (files.id=file)
            WHERE changeset=%s
         ORDER BY files.path""",
        (changeset.id,))
    def cache_key(args):
        return args[0].id, args[1]
    return list(FileChange.make(critic, ((changeset,) + row for row in cursor),
                                cache_key=cache_key))
