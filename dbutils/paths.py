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

def find_directory(db, path):
    path = path.strip("/")

    cursor = db.cursor()
    cursor.execute("SELECT finddirectory(%s)", (path,))

    row = cursor.fetchone()

    if row and row[0] is not None:
        return row[0]

    if "/" in path:
        directory, name = path.rsplit("/", 1)
        directory_id = find_directory(db, directory)
    else:
        directory_id, name = 0, path

    cursor.execute("INSERT INTO directories (directory, name) VALUES (%s, %s) RETURNING id", (directory_id, name))
    return cursor.fetchone()[0]

def is_directory(db, path):
    cursor = db.cursor()
    cursor.execute("SELECT finddirectory(%s)", (path,))

    directory_id = cursor.fetchone()[0]

    if directory_id is None: return False

    cursor.execute("SELECT 1 FROM files WHERE directory=%s LIMIT 1", (directory_id,))
    if cursor.fetchone(): return True

    cursor.execute("SELECT 1 FROM directories WHERE directory=%s LIMIT 1", (directory_id,))
    if cursor.fetchone(): return True

    return False

def is_file(db, path):
    cursor = db.cursor()
    cursor.execute("SELECT findfile(%s)", (path,))

    file_id = cursor.fetchone()[0]

    if file_id is None: return False

    cursor.execute("SELECT 1 FROM fileversions WHERE file=%s LIMIT 1", (file_id,))
    if cursor.fetchone(): return True

    return False

def find_file(db, path):
    path = path.lstrip("/")

    assert not path.endswith("/")

    cursor = db.cursor()
    cursor.execute("SELECT findfile(%s)", (path,))

    row = cursor.fetchone()

    if row and row[0] is not None:
        return row[0]

    if "/" in path:
        directory, name = path.rsplit("/", 1)
        directory_id = find_directory(db, directory)
    else:
        directory_id, name = 0, path

    cursor.execute("INSERT INTO files (directory, name) VALUES (%s, %s) RETURNING id", (directory_id, name))
    return cursor.fetchone()[0]

def find_files(db, files):
    for file in files:
        file.id = find_file(db, path=file.path)

def find_directory_file(db, path):
    path = path.lstrip("/")

    assert not path.endswith("/")

    file_id = find_file(db, path)
    if "/" in path:
        directory_id = find_directory(db, path.rsplit("/", 1)[0])
    else:
        directory_id = 0
    return directory_id, file_id

def describe_directory(db, directory_id):
    cursor = db.cursor()
    cursor.execute("SELECT fulldirectoryname(%s)", (directory_id,))
    return cursor.fetchone()[0].rstrip("/")

def describe_file(db, file_id):
    cursor = db.cursor()
    cursor.execute("SELECT fullfilename(%s)", (file_id,))
    return cursor.fetchone()[0]

def explode_path(db, invalid=None, file_id=None, directory_id=None):
    assert invalid is None
    assert (file_id is None) != (directory_id is None)

    cursor = db.cursor()
    path = []

    if file_id is not None:
        cursor.execute("SELECT * FROM filepath(%s)", (file_id,))
    else:
        path.append(directory_id)
        if not directory_id: return path
        cursor.execute("SELECT * FROM directorypath(%s)", (directory_id,))

    for (directory_id,) in cursor:
        path.insert(0, directory_id)

    return path

def contained_files(db, directory_id):
    cursor = db.cursor()
    cursor.execute("SELECT file_out FROM containedfiles(%s)", (directory_id,))
    return [file_id for (file_id,) in cursor]
