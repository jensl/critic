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

class InvalidFileId(Exception):
    def __init__(self, file_id):
        super(InvalidFileId, self).__init__("Invalid file id: %d" % file_id)

class InvalidPath(Exception):
    pass

class File(object):
    def __init__(self, file_id, path):
        self.id = file_id
        self.path = path

    def __int__(self):
        return self.id
    def __str__(self):
        return self.path

    @staticmethod
    def fromId(db, file_id):
        return File(file_id, describe_file(db, file_id))

    @staticmethod
    def fromPath(db, path, insert=True):
        file_id = find_file(db, path, insert)
        if file_id is None:
            # Only happens when insert=False.
            raise InvalidPath("Path does not exist: %s" % path)
        return File(file_id, path)

def find_file(db, path, insert=True):
    path = path.lstrip("/")

    if path.endswith("/"):
        raise InvalidPath("Trailing path separator: %r" % path)

    cursor = db.cursor()
    cursor.execute("SELECT id, path FROM files WHERE MD5(path)=MD5(%s)", (path,))

    row = cursor.fetchone()

    if row:
        file_id, found_path = row
        assert path == found_path, "MD5 collision in files table: %r != %r" % (path, found_path)
        return file_id

    if insert:
        cursor.execute("INSERT INTO files (path) VALUES (%s) RETURNING id", (path,))
        return cursor.fetchone()[0]

    return None

def find_files(db, files):
    for file in files:
        file.id = find_file(db, file.path)

def describe_file(db, file_id):
    cursor = db.cursor()
    cursor.execute("SELECT path FROM files WHERE id=%s", (file_id,))
    row = cursor.fetchone()
    if not row:
        raise InvalidFileId(file_id)
    return row[0]
