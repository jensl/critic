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

class FilecontentError(api.APIError):
    pass

class Filecontent(api.APIObject):
    """Representation of some context"""

    def getLines(self, first_row=None, last_row=None):
        assert first_row is None or isinstance(first_row, int)
        assert last_row is None or isinstance(last_row, int)

        return self._impl.getLines(first_row, last_row)

class Line:
    """Representation of a line from some version of a file"""
    def __init__(self, parts, offset):
        self.__parts = parts
        self.__offset = offset

    @property
    def parts(self):
        return self.__parts

    @property
    def offset(self):
        return self.__offset

def fetch(critic, repository, blob_sha1, file_obj):
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(repository, api.repository.Repository)
    assert isinstance(blob_sha1, str)
    assert isinstance(file_obj, api.file.File)

    return api.impl.filecontent.fetch(critic, repository, blob_sha1, file_obj)
