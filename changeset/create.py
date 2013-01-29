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

import dbutils
import gitutils
import diff.merge
import diff.parse

def createChangeset(db, request):
    repository_name = request["repository_name"]
    changeset_type = request["changeset_type"]

    repository = gitutils.Repository.fromName(db, repository_name)

    def insertChangeset(db, parent, child, files):
        while True:
            # Inserting new files will often clash when creating multiple
            # related changesets in parallel.  It's a simple operation, so if it
            # fails with an integrity error, just try again until it doesn't
            # fail.  (It will typically succeed the second time because then the
            # new files already exist, and it doesn't need to insert anything.)
            try:
                dbutils.find_files(db, files)
                db.commit()
                break
            except dbutils.IntegrityError:
                if repository_name == "chromium":
                    raise Exception, repr((parent, child, files))
                db.rollback()

        cursor = db.cursor()
        cursor.execute("INSERT INTO changesets (type, parent, child) VALUES (%s, %s, %s) RETURNING id",
                       (changeset_type, parent.getId(db) if parent else None, child.getId(db)))
        changeset_id = cursor.fetchone()[0]

        fileversions_values = []
        chunks_values = []

        file_ids = set()

        for file in files:
            if file.id in file_ids: raise Exception, "duplicate:%d:%s" % (file.id, file.path)
            file_ids.add(file.id)

            fileversions_values.append((changeset_id, file.id, file.old_sha1, file.new_sha1, file.old_mode, file.new_mode))

            for index, chunk in enumerate(file.chunks):
                chunk.analyze(file, index == len(file.chunks) - 1)
                chunks_values.append((changeset_id, file.id, chunk.delete_offset, chunk.delete_count, chunk.insert_offset, chunk.insert_count, chunk.analysis, 1 if chunk.is_whitespace else 0))

            file.clean()

        if fileversions_values:
            cursor.executemany("""INSERT INTO fileversions (changeset, file, old_sha1, new_sha1, old_mode, new_mode)
                                       VALUES (%s, %s, %s, %s, %s, %s)""",
                               fileversions_values)
        if chunks_values:
            cursor.executemany("""INSERT INTO chunks (changeset, file, deleteOffset, deleteCount, insertOffset, insertCount, analysis, whitespace)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                               chunks_values)

        return changeset_id

    changeset_ids = request["changeset_ids"] = {}

    child = gitutils.Commit.fromSHA1(db, repository, request["child_sha1"])

    cursor = db.cursor()

    if "parent_sha1" in request:
        assert changeset_type in ("custom", "conflicts")

        parent_sha1 = request["parent_sha1"]
        parent = gitutils.Commit.fromSHA1(db, repository, parent_sha1)

        cursor.execute("""SELECT id, %s
                            FROM changesets
                           WHERE type=%s
                             AND parent=%s
                             AND child=%s""",
                       (parent_sha1, changeset_type, parent.getId(db), child.getId(db)))
    else:
        assert changeset_type in ("direct", "merge")

        cursor.execute("""SELECT changesets.id, commits.sha1
                            FROM changesets
                 LEFT OUTER JOIN commits ON (commits.id=changesets.parent)
                           WHERE type=%s
                             AND child=%s""",
                       (changeset_type, child.getId(db)))

    rows = cursor.fetchall()

    if rows:
        # Changeset(s) already exists in database.

        for changeset_id, parent_sha1 in rows:
            changeset_ids[parent_sha1] = changeset_id
    else:
        # Parse diff and insert changeset(s) into the database.

        if changeset_type == "merge":
            changes = diff.merge.parseMergeDifferences(db, repository, child)
        elif changeset_type == "direct":
            changes = diff.parse.parseDifferences(repository, commit=child)
        else:
            changes = diff.parse.parseDifferences(repository, from_commit=parent, to_commit=child)

        for parent_sha1, files in changes.items():
            if parent_sha1 is None: parent = None
            else: parent = gitutils.Commit.fromSHA1(db, repository, parent_sha1)
            changeset_ids[parent_sha1] = insertChangeset(db, parent, child, files)

        db.commit()
