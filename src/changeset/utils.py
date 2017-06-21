# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

from subprocess import Popen as process, PIPE
from sys import argv, stderr, exit
import re
from dbutils import find_file, describe_file
import gitutils
import syntaxhighlight
import syntaxhighlight.request
from diffutils import expandWithContext
from htmlutils import htmlify, jsify
from time import strftime

import diff
import diff.analyze
import diff.parse
import diff.merge

import load
import dbutils
import client

def createFullMergeChangeset(db, user, repository, commit, **kwargs):
    assert len(commit.parents) > 1

    changesets = createChangeset(db, user, repository, commit, **kwargs)

    assert len(changesets) == len(commit.parents)

    replayed = createChangeset(db, user, repository, commit, conflicts=True, **kwargs)

    assert len(replayed) == 1

    changesets.append(replayed[0])

    return changesets

def createChangesets(db, repository, commits):
    cursor = db.readonly_cursor()
    requests = []

    for commit in commits:
        if len(commit.parents) > 1: changeset_type = 'merge'
        else: changeset_type = 'direct'

        cursor.execute("SELECT 1 FROM changesets WHERE child=%s AND type=%s", (commit.getId(db), changeset_type))

        if not cursor.fetchone():
            requests.append({ "repository_name": repository.name,
                              "changeset_type": changeset_type,
                              "child_sha1": commit.sha1 })

    if requests:
        db.refresh()

        client.requestChangesets(requests)

        db.refresh()

def createChangeset(db, user, repository, commit=None, from_commit=None, to_commit=None, rescan=False, reanalyze=False, conflicts=False, filtered_file_ids=None, review=None, do_highlight=True, load_chunks=True):
    if conflicts:
        if commit:
            assert len(commit.parents) > 1

            cursor = db.readonly_cursor()
            cursor.execute("SELECT replay FROM mergereplays WHERE original=%s", (commit.getId(db),))
            row = cursor.fetchone()

            if row:
                replay = gitutils.Commit.fromId(db, repository, row[0])
            else:
                replay = repository.replaymerge(db, user, commit)
                if not replay:
                    return None
                with db.updating_cursor("mergereplays") as cursor:
                    cursor.execute(
                        """INSERT INTO mergereplays (original, replay)
                                VALUES (%s, %s)""",
                        (commit.getId(db), replay.getId(db)))

            from_commit = replay
            to_commit = commit

            parents = [replay]
        else:
            parents = [from_commit]
            commit = to_commit

        changeset_type = 'conflicts'
    elif commit:
        parents = [gitutils.Commit.fromSHA1(db, repository, sha1) for sha1 in commit.parents] or [None]
        changeset_type = 'merge' if len(parents) > 1 else 'direct'
    else:
        parents = [from_commit]
        commit = to_commit
        changeset_type = 'direct' if len(to_commit.parents) == 1 and from_commit == to_commit.parents[0] else 'custom'

    changesets = []

    thin_diff = False

    changeset_ids = []

    cursor = db.readonly_cursor()

    for parent in parents:
        if parent:
            cursor.execute("SELECT id FROM changesets WHERE parent=%s AND child=%s AND type=%s",
                           (parent.getId(db), commit.getId(db), changeset_type))
        else:
            cursor.execute("SELECT id FROM changesets WHERE parent IS NULL AND child=%s AND type=%s",
                           (commit.getId(db), changeset_type))

        changeset_ids.extend(changeset_id for (changeset_id,) in cursor)

    assert len(changeset_ids) in (0, len(parents))

    if changeset_ids:
        if rescan and user.hasRole(db, "developer"):
            with db.updating_cursor("changesets") as cursor:
                cursor.execute(
                    """DELETE
                         FROM changesets
                        WHERE id=ANY (%s)""",
                    (changeset_ids,))

            changeset_ids = []
        else:
            if changeset_type == 'custom':
                with db.updating_cursor("customchangesets") as cursor:
                    cursor.execute(
                        """UPDATE customchangesets
                              SET time=NOW()
                            WHERE changeset=ANY (%s)""",
                        (changeset_ids,))

            for changeset_id in changeset_ids:
                changeset = load.loadChangeset(db, repository, changeset_id, filtered_file_ids=filtered_file_ids, load_chunks=load_chunks)
                changeset.conflicts = conflicts
                changesets.append(changeset)

            if reanalyze and user.hasRole(db, "developer"):
                for changeset in changesets:
                    analysis_values = []

                    for file in changeset.files:
                        if not filtered_file_ids or file.id in filtered_file_ids:
                            for index, chunk in enumerate(file.chunks):
                                old_analysis = chunk.analysis
                                chunk.analyze(file, index == len(file.chunks) - 1, True)
                                if old_analysis != chunk.analysis:
                                    analysis_values.append((chunk.analysis, chunk.id))

                if reanalyze == "commit" and analysis_values:
                    with db.updating_cursor("chunks") as cursor:
                        cursor.executemany(
                            """UPDATE chunks
                                  SET analysis=%s
                                WHERE id=%s""",
                            analysis_values)

    if not changesets:
        if len(parents) == 1 and from_commit and to_commit and filtered_file_ids:
            if from_commit.isAncestorOf(to_commit):
                iter_commit = to_commit
                while iter_commit != from_commit:
                    if len(iter_commit.parents) > 1:
                        thin_diff = True
                        break
                    iter_commit = gitutils.Commit.fromSHA1(db, repository, iter_commit.parents[0])
            else:
                thin_diff = True

        if not thin_diff:
            if changeset_type == "direct":
                request = { "changeset_type": "direct",
                            "child_sha1": commit.sha1 }
            elif changeset_type == "custom":
                request = { "changeset_type": "custom",
                            "parent_sha1": from_commit.sha1 if from_commit else "0" * 40,
                            "child_sha1": to_commit.sha1 }
            elif changeset_type == "merge":
                request = { "changeset_type": "merge",
                            "child_sha1": commit.sha1 }
            else:
                request = { "changeset_type": "conflicts",
                            "parent_sha1": from_commit.sha1,
                            "child_sha1": to_commit.sha1 }

            request["repository_name"] = repository.name

            db.refresh()

            client.requestChangesets([request])

            db.refresh()

            cursor = db.readonly_cursor()

            for parent in parents:
                if parent:
                    cursor.execute("SELECT id FROM changesets WHERE parent=%s AND child=%s AND type=%s",
                                   (parent.getId(db), commit.getId(db), changeset_type))
                else:
                    cursor.execute("SELECT id FROM changesets WHERE parent IS NULL AND child=%s AND type=%s",
                                   (commit.getId(db), changeset_type))

                changeset_id = cursor.fetchone()[0]
                changeset = load.loadChangeset(db, repository, changeset_id, filtered_file_ids=filtered_file_ids, load_chunks=load_chunks)
                changeset.conflicts = conflicts

                changesets.append(changeset)
        else:
            changes = diff.parse.parseDifferences(repository, from_commit=from_commit, to_commit=to_commit, filter_paths=[describe_file(db, file_id) for file_id in filtered_file_ids])[from_commit.sha1]

            dbutils.find_files(db, changes)

            for file in changes:
                for index, chunk in enumerate(file.chunks):
                    chunk.analyze(file, index == len(file.chunks) - 1)

            changeset = diff.Changeset(None, from_commit, to_commit, changeset_type)
            changeset.conflicts = conflicts
            changeset.files = diff.File.sorted(changes)

            changesets.append(changeset)

    if do_highlight:
        highlights = {}

        for changeset in changesets:
            for file in changeset.files:
                if file.canHighlight():
                    if file.old_sha1 and file.old_sha1 != '0' * 40:
                        highlights[file.old_sha1] = (file.path, file.getLanguage())
                    if file.new_sha1 and file.new_sha1 != '0' * 40:
                        highlights[file.new_sha1] = (file.path, file.getLanguage())

        syntaxhighlight.request.requestHighlights(repository, highlights, "legacy")

    return changesets

def getCodeContext(db, sha1, line, minimized=False):
    cursor = db.readonly_cursor()
    cursor.execute("SELECT context FROM codecontexts WHERE sha1=%s AND first_line<=%s AND last_line>=%s ORDER BY first_line DESC LIMIT 1", [sha1, line, line])
    row = cursor.fetchone()
    if row:
        context = row[0]
        if minimized: context = re.sub("\\(.*(?:\\)|...$)", "(...)", context)
        return context
    else: return None
