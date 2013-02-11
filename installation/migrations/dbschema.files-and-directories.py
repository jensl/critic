# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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

import sys
import psycopg2
import json
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("--uid", type=int)
parser.add_argument("--gid", type=int)

arguments = parser.parse_args()

os.setgid(arguments.gid)
os.setuid(arguments.uid)

data = json.load(sys.stdin)

import configuration

db = psycopg2.connect(**configuration.database.PARAMETERS)
cursor = db.cursor()

def column_exists(table, column):
    try:
        cursor.execute("SELECT %s FROM %s LIMIT 1" % (column, table))
        return True
    except psycopg2.ProgrammingError:
        db.rollback()
        return False

added = [column_exists("files", "path"),
         column_exists("filters", "path"),
         column_exists("reviewfilters", "path")]

removed = [column_exists("files", "directory"),
           column_exists("files", "name"),
           column_exists("filters", "directory"),
           column_exists("filters", "file"),
           column_exists("reviewfilters", "directory"),
           column_exists("reviewfilters", "file"),
           column_exists("directories", "id")]

if all(added) and not any(removed):
    # All expected modifications appear to have taken place already.
    sys.exit(0)
elif any(added) or not all(removed):
    # Some modifications appear to have taken place already, but not
    # all.  This is bad, and possibly unrecoverable.  It's probably
    # not a good idea to just run the commands below.
    sys.stderr.write("""\
The database schema appears to be in an inconsistent state!

Please see installation/migrations/dbschema.files-and-directories.py
and try to figure out which of the commands in it to run.

Alternatively, restore a database backup from before the previous
upgrade attempt, and then try running upgrade.py again.
""")
    sys.exit(1)

# Add 'path' column to 'files' table.
cursor.execute("ALTER TABLE files ADD path TEXT")
cursor.execute("UPDATE files SET path=fullfilename(id)")
cursor.execute("ALTER TABLE files ALTER path SET NOT NULL")
cursor.execute("CREATE UNIQUE INDEX files_path_md5 ON files (MD5(path))")
cursor.execute("CREATE INDEX files_path_gin ON files USING gin (STRING_TO_ARRAY(path, '/'))")

# Modify 'filters' table similarly.
cursor.execute("ALTER TABLE filters ADD path TEXT")
cursor.execute("UPDATE filters SET path=fullfilename(file) WHERE file>0")
cursor.execute("UPDATE filters SET path=COALESCE(NULLIF(fulldirectoryname(directory), ''), '/') WHERE file=0")
cursor.execute("ALTER TABLE filters ALTER path SET NOT NULL")
cursor.execute("CREATE UNIQUE INDEX filters_repository_uid_path_md5 ON filters (repository, uid, MD5(path))")

# Modify 'reviewfilters' table similarly.
cursor.execute("ALTER TABLE reviewfilters ADD path TEXT")
cursor.execute("UPDATE reviewfilters SET path=fullfilename(file) WHERE file>0")
cursor.execute("UPDATE reviewfilters SET path=COALESCE(NULLIF(fulldirectoryname(directory), ''), '/') WHERE file=0")
cursor.execute("ALTER TABLE reviewfilters ALTER path SET NOT NULL")
cursor.execute("CREATE UNIQUE INDEX reviewfilters_review_uid_path_md5 ON reviewfilters (review, uid, MD5(path))")

# Modify 'reviewfilterchanges' table similarly.
cursor.execute("ALTER TABLE reviewfilterchanges ADD path TEXT")
cursor.execute("UPDATE reviewfilterchanges SET path=fullfilename(file) WHERE file>0")
cursor.execute("UPDATE reviewfilterchanges SET path=fulldirectoryname(directory) WHERE file=0")
cursor.execute("ALTER TABLE reviewfilterchanges ALTER path SET NOT NULL")

# Drop the now redundant 'directories' table.
cursor.execute("ALTER TABLE files DROP directory, DROP name")
cursor.execute("ALTER TABLE filters DROP directory, DROP file, DROP specificity")
cursor.execute("ALTER TABLE reviewfilters DROP directory, DROP file")
cursor.execute("ALTER TABLE reviewfilterchanges DROP directory, DROP file")
cursor.execute("DROP TABLE directories")

# Drop various utility functions that are no longer necessary.
cursor.execute("DROP FUNCTION IF EXISTS filepath()")
cursor.execute("DROP FUNCTION IF EXISTS directorypath()")
cursor.execute("DROP FUNCTION IF EXISTS subdirectories()")
cursor.execute("DROP FUNCTION IF EXISTS containedfiles()")
cursor.execute("DROP FUNCTION IF EXISTS fullfilename()")
cursor.execute("DROP FUNCTION IF EXISTS fulldirectoryname()")
cursor.execute("DROP FUNCTION IF EXISTS findfile()")
cursor.execute("DROP FUNCTION IF EXISTS finddirectory()")

db.commit()

# ALTER TYPE ... ADD VALUE cannot be executed inside a transaction block.
db.autocommit = True
# Add filter type "ignored".
cursor.execute("ALTER TYPE filtertype ADD VALUE 'ignored'")

db.close()
