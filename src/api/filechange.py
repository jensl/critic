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

class FilechangeError(api.APIError):
    pass

class Filechange(api.APIObject):
    """Representation of the changes to a file introduced by a changeset"""

    @property
    def id(self):
        return self._impl.id

    @property
    def changeset(self):
        return self._impl.changeset

    @property
    def path(self):
        return self._impl.path

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

    @property
    def chunks(self):
        return self._impl.chunks


class Chunk(api.APIObject):
    """A change to a file"""

    @property
    def id(self):
        return self._impl.id

    @property
    def deleteoffset(self):
        return self._impl.deleteoffset

    @property
    def deletecount(self):
        return self._impl.deletecount

    @property
    def insertoffset(self):
        return self._impl.insertoffset

    @property
    def insertcount(self):
        return self._impl.insertcount

    @property
    def analysis(self):
        return self._impl.analysis

    @property
    def is_whitespace(self):
        return self._impl.is_whitespace


def fetch(critic, changeset, file_id):
    return api.impl.filechange.fetch(critic, changeset, file_id)

def fetchAll(critic, changeset):
    return api.impl.filechange.fetchAll(critic, changeset)
