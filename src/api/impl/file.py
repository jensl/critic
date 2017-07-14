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
import apiobject
import dbutils

class File(apiobject.APIObject):
    wrapper_class = api.file.File

    def __init__(self, file_id, path):
        self.id = file_id
        self.path = path

def _fetch_by_ids(critic, file_ids):
    # FIXME: Optimize this to do a single database query. Currently, there will
    # be one (fast) query per file.
    try:
        for file_id in file_ids:
            internal = dbutils.File.fromId(critic.database, file_id)
            yield (int(internal), str(internal))
    except dbutils.InvalidFileId:
        raise api.file.InvalidFileId(file_id)

def _fetch_by_paths(critic, paths, create):
    # FIXME: Optimize this to do a single database query. Currently, there will
    # be one (fast) query per file.
    try:
        for path in paths:
            internal = dbutils.File.fromPath(
                critic.database, path, insert=create)
            yield (int(internal), str(internal))
    except dbutils.InvalidPath:
        raise api.file.InvalidPath(path)

@File.cached()
def fetch(critic, file_id, path, create):
    if file_id is not None:
        items = _fetch_by_ids(critic, [file_id])
    else:
        items = _fetch_by_paths(critic, [path], create)
    return next(File.make(critic, items))

def fetchMany(critic, file_ids, paths, create):
    if file_ids is not None:
        items = _fetch_by_ids(critic, file_ids)
    else:
        items = _fetch_by_paths(critic, paths, create)
    return list(File.make(critic, items))
