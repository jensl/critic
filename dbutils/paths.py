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

def find_file(db, path):
    path = path.lstrip("/")

    assert not path.endswith("/")

    cursor = db.cursor()
    cursor.execute("SELECT id, path FROM files WHERE MD5(path)=MD5(%s)", (path,))

    row = cursor.fetchone()

    if row:
        file_id, found_path = row
        assert path == found_path, "MD5 collision in files table: %r != %r" % (path, found_path)
        return file_id

    cursor.execute("INSERT INTO files (path) VALUES (%s) RETURNING id", (path,))
    return cursor.fetchone()[0]

def find_files(db, files):
    for file in files:
        file.id = find_file(db, file.path)

def describe_file(db, file_id):
    cursor = db.cursor()
    cursor.execute("SELECT path FROM files WHERE id=%s", (file_id,))
    return cursor.fetchone()[0]
