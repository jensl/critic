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


def fetch(critic, repository, changeset_id, from_commit, to_commit,
          single_commit, review, automatic):
    if changeset_id is not None:
        return fetch_by_id(critic, repository, changeset_id)

    if review and automatic:
        # Handle automatic changesets using legacy code, and by setting the
        # |from_commit|/|to_commit| or |single_commit| arguments.
        import dbutils
        import request
        import page.showcommit

        legacy_user = dbutils.User.fromAPI(critic.effective_user)
        legacy_review = dbutils.Review.fromAPI(review)

        try:
            from_sha1, to_sha1, all_commits, listed_commits = \
                page.showcommit.commitRangeFromReview(
                    critic.database, legacy_user, legacy_review, automatic, [])
        except request.DisplayMessage:
            # FIXME: This error message could be better. The legacy code does
            # report more useful error messages, but does it in a way that's
            # pretty tied to the old HTML UI. Some refactoring is needed.
            raise api.changeset.ChangesetError("Automatic mode failed")
        except page.showcommit.NoChangesFound:
            assert automatic != "everything"
            raise api.changeset.AutomaticChangesetEmpty("No %s changes found"
                                                        % automatic)

        from_commit = api.commit.fetch(repository, sha1=from_sha1)
        to_commit = api.commit.fetch(repository, sha1=to_sha1)

        if from_commit == to_commit:
            single_commit = to_commit
            from_commit = to_commit = None

    if from_commit and to_commit:
        changeset_id = get_changeset_id(
            critic, repository, from_commit, to_commit)
        if changeset_id is not None:
            return fetch_by_id(critic, repository, changeset_id)
        request_changeset_creation(
            critic, repository.name, "custom", from_commit=from_commit,
            to_commit=to_commit)
        raise api.changeset.ChangesetDelayed()

    assert single_commit

    if len(single_commit.parents) > 0:
        from_commit = single_commit.parents[0]
    else:
        from_commit = None
    changeset_id = get_changeset_id(
        critic, repository, from_commit, single_commit)
    if changeset_id is not None:
        return fetch_by_id(critic, repository, changeset_id)
    request_changeset_creation(
        critic, repository.name, "direct", to_commit=single_commit)
    raise api.changeset.ChangesetDelayed()


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


def get_changeset_id(critic, repository, from_commit, to_commit):
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
