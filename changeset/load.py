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

import diff
import dbutils
import gitutils

def loadChangeset(db, repository, changeset_id, filtered_file_ids=None, load_chunks=True):
    return loadChangesets(db, repository,
                          changesets=[diff.Changeset.fromId(db, repository, changeset_id)],
                          filtered_file_ids=filtered_file_ids,
                          load_chunks=load_chunks)[0]

def loadChangesetsForCommits(db, repository, commits, filtered_file_ids=None, load_chunks=True):
    commit_ids = dict([(commit.getId(db), commit) for commit in commits])

    def getCommit(commit_id):
        return commit_ids.get(commit_id) or gitutils.Commit.fromId(db, repository, commit_id)

    cursor = db.cursor()
    cursor.execute("SELECT id, parent, child FROM changesets WHERE child=ANY (%s) AND type='direct'", (commit_ids.keys(),))

    changesets = []

    for changeset_id, parent_id, child_id in cursor:
        changesets.append(diff.Changeset(changeset_id, getCommit(parent_id), getCommit(child_id), "direct"))

    return loadChangesets(db, repository, changesets, filtered_file_ids=filtered_file_ids, load_chunks=load_chunks)

def loadChangesets(db, repository, changesets, filtered_file_ids=None, load_chunks=True):
    cursor = db.cursor()

    changeset_ids = [changeset.id for changeset in changesets]
    filtered_file_ids = list(filtered_file_ids) if filtered_file_ids else None

    if filtered_file_ids is None:
        cursor.execute("""SELECT changeset, file, fullfilename(file), old_sha1, new_sha1, old_mode, new_mode
                            FROM fileversions
                            WHERE changeset=ANY (%s)""",
                       (changeset_ids,))
    else:
        cursor.execute("""SELECT changeset, file, fullfilename(file), old_sha1, new_sha1, old_mode, new_mode
                            FROM fileversions
                            WHERE changeset=ANY (%s)
                              AND file=ANY (%s)""",
                       (changeset_ids, filtered_file_ids))

    files = dict([(changeset.id, {}) for changeset in changesets])

    for changeset_id, file_id, file_path, file_old_sha1, file_new_sha1, file_old_mode, file_new_mode in cursor.fetchall():
        files[changeset_id][file_id] = diff.File(file_id, file_path,
                                                 file_old_sha1, file_new_sha1,
                                                 repository,
                                                 old_mode=file_old_mode,
                                                 new_mode=file_new_mode,
                                                 chunks=[])

    if load_chunks:
        if filtered_file_ids is None:
            cursor.execute("""SELECT id, changeset, file, deleteOffset, deleteCount, insertOffset, insertCount, analysis, whitespace
                                FROM chunks
                                WHERE changeset=ANY (%s)
                                ORDER BY file, deleteOffset ASC""",
                           (changeset_ids,))
        else:
            cursor.execute("""SELECT id, changeset, file, deleteOffset, deleteCount, insertOffset, insertCount, analysis, whitespace
                                FROM chunks
                                WHERE changeset=ANY (%s)
                                  AND file=ANY (%s)
                                ORDER BY file, deleteOffset ASC""",
                           (changeset_ids, filtered_file_ids))

        for chunk_id, changeset_id, file_id, delete_offset, delete_count, insert_offset, insert_count, analysis, is_whitespace in cursor:
            files[changeset_id][file_id].chunks.append(diff.Chunk(delete_offset, delete_count,
                                                                  insert_offset, insert_count,
                                                                  id=chunk_id,
                                                                  is_whitespace=is_whitespace,
                                                                  analysis=analysis))

    for changeset in changesets:
        changeset.files = diff.File.sorted(files[changeset.id].values())

    return changesets
