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
import diff

class Filechange(apiobject.APIObject):
    wrapper_class = api.filechange.Filechange

    def __init__(self, id, changeset, path, old_sha1, old_mode,
                 new_sha1, new_mode, chunks):
        self.id = id
        self.changeset = changeset
        self.path = path
        self.old_sha1 = old_sha1
        self.old_mode = old_mode
        self.new_sha1 = new_sha1
        self.new_mode = new_mode
        self.chunks = chunks


class Chunk(apiobject.APIObject):
    wrapper_class = api.filechange.Chunk

    def __init__(self, deleteoffset, deletecount, insertoffset, insertcount, analysis, is_whitespace):
        self.deleteoffset = deleteoffset
        self.deletecount = deletecount
        self.insertoffset = insertoffset
        self.insertcount = insertcount
        self.analysis = analysis
        self.is_whitespace = is_whitespace


def fetch(critic, changeset, id):
    cursor = critic.getDatabaseCursor()
    cursor.execute(
        """SELECT deleteoffset, deletecount, insertoffset, insertcount,
                      analysis, whitespace
             FROM chunks
            WHERE changeset=%s AND file=%s
         ORDER BY deleteoffset ASC""",
        (changeset.id, id))
    chunks = list(Chunk.make(critic, cursor))

    cursor.execute(
        """SELECT path, old_sha1, old_mode, new_sha1, new_mode
             FROM files
       INNER JOIN fileversions ON files.id=fileversions.file
            WHERE fileversions.changeset=%s AND files.id=%s""",
        (changeset.id, id,))
    row = cursor.fetchone()
    (path, old_sha1, old_mode, new_sha1, new_mode) = row
    filechange = Filechange(id, changeset, path, old_sha1, old_mode,
                            new_sha1, new_mode, chunks)
    return filechange.wrap(critic)

def fetchAll(critic, changeset):
    cursor = critic.getDatabaseCursor()

    cursor.execute(
        """SELECT file, deleteoffset, deletecount, insertoffset, insertcount,
                            analysis, whitespace
             FROM chunks
            WHERE changeset=%s
         ORDER BY deleteoffset ASC""",
        (changeset.id,))
    rows = cursor.fetchall()

    filechunks = {}
    for row in rows:
        (id, deleteoffset, deletecount, insertoffset,
         insertcount, analysis, is_whitespace) = row
        chunk = Chunk(deleteoffset, deletecount, insertoffset, insertcount,
                      analysis, is_whitespace)
        if id in filechunks:
            filechunks[id].append(chunk)
        else:
            filechunks[id] = [chunk]


    cursor.execute(
        """SELECT files.id, path, old_sha1, old_mode, new_sha1, new_mode
             FROM files
       INNER JOIN fileversions ON files.id=fileversions.file
            WHERE fileversions.changeset=%s""",
        (changeset.id,))
    rows = cursor.fetchall()

    files = []
    for row in rows:
        (id, path, old_sha1, old_mode, new_sha1, new_mode) = row
        chunks = filechunks[id]
        files.append(Filechange(id, changeset, path, old_sha1, old_mode,
                                new_sha1, new_mode, chunks).wrap(critic))

    return sorted(files, key=lambda file: file.path)
