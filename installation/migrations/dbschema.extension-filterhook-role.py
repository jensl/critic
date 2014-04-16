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
import re

parser = argparse.ArgumentParser()
parser.add_argument("--uid", type=int)
parser.add_argument("--gid", type=int)

arguments = parser.parse_args()

os.setgid(arguments.gid)
os.setuid(arguments.uid)

import configuration

db = psycopg2.connect(**configuration.database.PARAMETERS)
cursor = db.cursor()

def table_exists(table_name):
    try:
        cursor.execute("SELECT 1 FROM %s" % table_name)

        # Above statement would have thrown a psycopg2.ProgrammingError if the
        # table didn't exist, but it didn't, so the table must exist.
        return True
    except psycopg2.ProgrammingError:
        db.rollback()
        return False

def createtable(statement):
    (table_name,) = re.search("CREATE TABLE (\w+)", statement).groups()

    # Make sure the table doesn't already exist.
    if not table_exists(table_name):
        cursor.execute(statement)
        db.commit()

def createindex(statement):
    (index_name,) = re.search("CREATE INDEX (\w+)", statement).groups()

    cursor.execute("DROP INDEX IF EXISTS %s" % index_name)
    cursor.execute(statement)
    db.commit()

def run_statements(statements):
    for statement in statements.split(";"):
        statement = statement.strip()

        if not statement:
            pass
        elif statement.startswith("CREATE TABLE"):
            createtable(statement)
        elif statement.startswith("CREATE INDEX"):
            createindex(statement)
        else:
            print >>sys.stderr, "Unexpected SQL statement: %r" % statement
            sys.exit(1)

# First check if dbschema.extensions.sql has been loaded at all.  It wasn't
# until extension support (the extend.py script) was fully added.  If the
# 'extensions' table doesn't exist, it obviously hasn't, and the tables below
# would be added along with everything else when dbschema.extensions.sql is
# loaded by extend.py.
#
# Also, the statements below depend on the basic extensions tables existing due
# to foreign keys they set up.
if not table_exists("extensions"):
    sys.exit(0)

run_statements("""

CREATE TABLE extensionfilterhookroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,
    title VARCHAR(64) NOT NULL,
    role_description TEXT,
    data_description TEXT );

CREATE TABLE extensionhookfilters
  ( id SERIAL PRIMARY KEY,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    extension INTEGER NOT NULL REFERENCES extensions ON DELETE CASCADE,
    repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,
    path TEXT NOT NULL,
    data TEXT );
CREATE INDEX extensionhookfilters_uid_extension
          ON extensionhookfilters (uid, extension);
CREATE INDEX extensionhookfilters_repository
          ON extensionhookfilters (repository);

CREATE TABLE extensionfilterhookevents
  ( id SERIAL PRIMARY KEY,
    filter INTEGER NOT NULL REFERENCES extensionhookfilters ON DELETE CASCADE,
    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    data TEXT );
CREATE TABLE extensionfilterhookcommits
  ( event INTEGER NOT NULL REFERENCES extensionfilterhookevents ON DELETE CASCADE,
    commit INTEGER NOT NULL REFERENCES commits );
CREATE INDEX extensionfilterhookcommits_event
          ON extensionfilterhookcommits (event);
CREATE TABLE extensionfilterhookfiles
  ( event INTEGER NOT NULL REFERENCES extensionfilterhookevents ON DELETE CASCADE,
    file INTEGER NOT NULL REFERENCES files );
CREATE INDEX extensionfilterhookfiles_event
          ON extensionfilterhookfiles (event);

""")

db.close()
