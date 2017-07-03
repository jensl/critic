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

    def __init__(self, id, changeset_type, from_commit_id, to_commit_id, files, repository):
        self.id = id
        self.type = changeset_type
        self.__from_commit_id = from_commit_id
        self.__to_commit_id = to_commit_id
        self.files = files
        self.__filediffs = None
        self.repository = repository

    def getFromCommit(self):
        if self.__from_commit_id is None:
            return None
        return api.commit.fetch(
            self.repository, commit_id=self.__from_commit_id)

    def getToCommit(self):
        if self.__to_commit_id is None:
            return None
        return api.commit.fetch(
            self.repository, commit_id=self.__to_commit_id)

    def getContributingCommits(self, critic):
        if self.__from_commit_id is None:
            return None
        try:
            return api.commitset.calculateFromRange(
                critic, self.getFromCommit(), self.getToCommit())
        except api.commitset.InvalidCommitRange:
            return None

    def getFileDiffs(self, wrapper):
        if self.__filediffs is None:
            if self.id is not None:
                # context_lines will only be relevant if we had requested the
                # content of the filediff
                self.__filediffs = api.filediff.fetchAll(
                    wrapper.critic, self.repository, wrapper, context_lines=3)
        return self.__filediffs


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
            return Changeset(None, "custom", None, None, None, repository).wrap(critic)
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
            return Changeset(None, "direct", None, None, None, repository).wrap(critic)


def fetch_by_id(critic, repository, changeset_id):
    try:
        return critic._impl.lookup(api.changeset.Changeset,
                                   (int(repository), changeset_id))
    except KeyError:
        pass

    cursor = critic.getDatabaseCursor()

    cursor.execute(
        """SELECT type, parent, child
             FROM changesets
            WHERE id=%s""",
        (changeset_id,))

    row = cursor.fetchone()

    if not row:
        raise api.changeset.InvalidChangesetId(id)

    (changeset_type, from_commit_id, to_commit_id) = row

    cursor.execute(
        """SELECT file
             FROM fileversions
            WHERE changeset=%s""",
        (changeset_id,))

    files = api.file.fetchMany(critic, (file_id for (file_id,) in cursor))

    changeset = Changeset(
        changeset_id, changeset_type, from_commit_id, to_commit_id,
        sorted(files, key=lambda file: file.path), repository).wrap(critic)

    critic._impl.assign(
        api.changeset.Changeset, (int(repository), changeset_id), changeset)

    return changeset


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
                "repository_name": repository_name}
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
