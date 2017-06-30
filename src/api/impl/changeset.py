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

from __future__ import absolute_import

import api
import api.impl
from api.impl import apiobject
import changeset.client
from gitutils import GitReferenceError
import diff

class Changeset(apiobject.APIObject):
    wrapper_class = api.changeset.Changeset

    def __init__(self, id, changeset_type, from_commit, to_commit, files):
        self.id = id
        self.type = changeset_type
        self.from_commit = from_commit
        self.to_commit = to_commit
        self.files = files


class File(apiobject.APIObject):
    wrapper_class = api.changeset.File

    def __init__(self, id, path):
        self.id = id
        self.path = path


def fetch(critic,
          repository,
          id=None,
          from_commit=None,
          to_commit=None,
          single_commit=None):

    if id is not None:
        return fetch_by_id(critic, repository, id)
    if from_commit and to_commit:
        id = get_changeset_id(critic,
                              repository,
                              from_commit=from_commit,
                              to_commit=to_commit)
        if id is not None:
            return fetch_by_id(critic, repository, id)
        else:
            request_changeset_creation(critic,
                                       repository.name,
                                       "custom",
                                       from_commit=from_commit,
                                       to_commit=to_commit)
            return Changeset(None, "custom", None, None, None).wrap(critic)
        return None
    if single_commit:
        if len(single_commit.parents) > 0:
            from_commit = single_commit.parents[0]
        else:
            from_commit = None
        id = get_changeset_id(critic,
                              repository,
                              from_commit=from_commit,
                              to_commit=single_commit)
        if id is not None:
            return fetch_by_id(critic, repository, id)
        else:
            request_changeset_creation(critic,
                                       repository.name,
                                       "direct",
                                       to_commit=single_commit)
            return Changeset(None, "direct", None, None, None).wrap(critic)


@Changeset.cached()
def fetch_by_id(critic, repository, id):
    cursor = critic.getDatabaseCursor()

    cursor.execute(
        """SELECT id, type, parent, child
             FROM changesets
            WHERE id=%s""",
        (id,))

    row = cursor.fetchone()

    if not row:
        raise api.changeset.InvalidChangesetId(id)

    (id, changeset_type, from_commit, to_commit) = row

    cursor.execute(
        """SELECT files.id, files.path
             FROM files
       INNER JOIN fileversions ON fileversions.file=files.id
       INNER JOIN changesets ON changesets.id=fileversions.changeset
            WHERE changesets.id=%s""",
        (id,))
    return Changeset(id, changeset_type, from_commit, to_commit, list(
        File.make(critic, cursor))).wrap(critic)
    

def get_changeset_id(critic, repository, from_commit=None, to_commit=None):
    cursor = critic.getDatabaseCursor()
    if from_commit:
        cursor.execute(
            """SELECT id
                 FROM changesets
                WHERE parent=%s AND child=%s""",
            (from_commit.id, to_commit.id))
    else:
        cursor.execute(
            """SELECT id
                 FROM changesets
                WHERE parent IS NULL AND child=%s""",
            (to_commit.id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        return None


def request_changeset_creation(critic,
                               repository_name,
                               changeset_type,
                               from_commit=None,
                               to_commit=None):
    request = { "changeset_type": changeset_type,
                "repository_name": "critic"}
    if changeset_type == "direct":
        request["child_sha1"] = to_commit.sha1
    elif changeset_type == "custom":
        request["parent_sha1"] = from_commit.sha1
        request["child_sha1"] = to_commit.sha1
    elif changeset_type == "merge":
        request["child_sha1"] = to_commit.sha1
    elif changeset_type == "conflicts":
        request["parent_sha1"] = from_commit.sha1
        request["child_sha1"] = to_commit.sha1
    try:
        changeset.client.requestChangesets([request], async=True)
    except changeset.client.ChangesetBackgroundServiceError as error:
        raise api.changeset.ChangesetBackgroundServiceError(error)
