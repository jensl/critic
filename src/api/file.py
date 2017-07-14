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

class FileError(api.APIError):
    pass

class InvalidFileId(FileError):
    """Raised when an invalid file id is used."""

    def __init__(self, file_id):
        """Constructor"""
        super(InvalidFileId, self).__init__(
            "Invalid file id: %d" % file_id)

class InvalidPath(FileError):
    """Raised when an invalid path is used."""

    def __init__(self, path):
        """Constructor"""
        super(InvalidPath, self).__init__(
            "Invalid path: %s" % path)

class File(api.APIObject):
    def __str__(self):
        return self.path

    @property
    def id(self):
        """The path's unique id"""
        return self._impl.id

    @property
    def path(self):
        """The path"""
        return self._impl.path

def fetch(critic, file_id=None, path=None, create=False):
    """Fetch a "file" (file id / path mapping)

       If a path is used, and |create| is True, a mapping is created if one
       didn't already exist."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert (file_id is None) != (path is None)
    if file_id is not None:
        file_id = int(file_id)
    if path is not None:
        path = str(path)
    assert isinstance(create, bool)
    return api.impl.file.fetch(critic, file_id, path, create)

def fetchMany(critic, file_ids=None, paths=None, create=False):
    """Fetch multiple "files" (file id / path mappings)

       If paths are used, and |create| is True, a mapping is created if one
       didn't already exist."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert (file_ids is None) != (paths is None)
    if file_ids is not None:
        file_ids = [int(file_id) for file_id in file_ids]
    if paths is not None:
        paths = [str(path) for path in paths]
    assert isinstance(create, bool)
    return api.impl.file.fetchMany(critic, file_ids, paths, create)
