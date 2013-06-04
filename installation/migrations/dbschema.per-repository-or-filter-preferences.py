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
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("--uid", type=int)
parser.add_argument("--gid", type=int)

arguments = parser.parse_args()

os.setgid(arguments.gid)
os.setuid(arguments.uid)

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

added = [column_exists("preferences", "per_system"),
         column_exists("preferences", "per_user"),
         column_exists("preferences", "per_repository"),
         column_exists("preferences", "per_filter"),
         column_exists("userpreferences", "repository"),
         column_exists("userpreferences", "filter")]

removed = [column_exists("preferences", "default_string"),
           column_exists("preferences", "default_integer")]

if all(added) and not any(removed):
    # All expected modifications appear to have taken place already.
    sys.exit(0)
elif any(added) or not all(removed):
    # Some modifications appear to have taken place already, but not
    # all.  This is bad, and possibly unrecoverable.  It's probably
    # not a good idea to just run the commands below.
    sys.stderr.write("""\
The database schema appears to be in an inconsistent state!

Please see
  installation/migrations/dbschema.per-repository-or-filter-preferences.py
and try to figure out which of the commands in it to run.

Alternatively, restore a database backup from before the previous
upgrade attempt, and then try running upgrade.py again.
""")
    sys.exit(1)

# Drop the exiting 'userpreferences' PRIMARY KEY, since it conflicts with having
# multiple settings for different repositories and filters.
cursor.execute("""ALTER TABLE userpreferences
                      DROP CONSTRAINT userpreferences_pkey""")

# Add new columns to 'preferences'.
cursor.execute("""ALTER TABLE preferences
                      ADD per_system BOOLEAN NOT NULL DEFAULT TRUE,
                      ADD per_user BOOLEAN NOT NULL DEFAULT TRUE,
                      ADD per_repository BOOLEAN NOT NULL DEFAULT FALSE,
                      ADD per_filter BOOLEAN NOT NULL DEFAULT FALSE""")

# Add new columns to 'userpreferences'.
cursor.execute("""ALTER TABLE userpreferences
                      ALTER uid DROP NOT NULL,
                      ADD repository INTEGER REFERENCES repositories ON DELETE CASCADE,
                      ADD filter INTEGER REFERENCES filters ON DELETE CASCADE""")

# Move current system-wide default values over to the 'userpreferences' table as
# rows with uid=NULL.
cursor.execute("""INSERT INTO userpreferences (item, integer, string)
                       SELECT item, default_integer, default_string
                         FROM preferences""")

# Drop old default value columns from 'preferences'.
cursor.execute("""ALTER TABLE preferences
                      DROP default_string,
                      DROP default_integer""")

# Add new constraints to 'userpreferences'.
cursor.execute("""ALTER TABLE userpreferences
                      ADD CONSTRAINT check_uid_filter
                               CHECK (filter IS NULL OR uid IS NOT NULL),
                      ADD CONSTRAINT check_repository_filter
                               CHECK (repository IS NULL OR filter IS NULL)""")

# Add indexes used to check various uniqueness requirements involving NULL
# values.
cursor.execute("""CREATE UNIQUE INDEX userpreferences_item
                                   ON userpreferences (item)
                                WHERE uid IS NULL
                                  AND repository IS NULL
                                  AND filter IS NULL""")
cursor.execute("""CREATE UNIQUE INDEX userpreferences_item_uid
                                   ON userpreferences (item, uid)
                                WHERE uid IS NOT NULL
                                  AND repository IS NULL
                                  AND filter IS NULL""")
cursor.execute("""CREATE UNIQUE INDEX userpreferences_item_repository
                                   ON userpreferences (item, repository)
                                WHERE uid IS NULL
                                  AND repository IS NOT NULL
                                  AND filter IS NULL""")
cursor.execute("""CREATE UNIQUE INDEX userpreferences_item_uid_repository
                                   ON userpreferences (item, uid, repository)
                                WHERE uid IS NOT NULL
                                  AND repository IS NOT NULL
                                  AND filter IS NULL""")
cursor.execute("""CREATE UNIQUE INDEX userpreferences_item_uid_filter
                                   ON userpreferences (item, uid, filter)
                                WHERE uid IS NOT NULL
                                  AND repository IS NULL
                                  AND filter IS NOT NULL""")

db.commit()
db.close()
