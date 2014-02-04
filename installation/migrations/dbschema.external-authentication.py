# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

def create(table_name, statement):
    try:
        # Make sure the table doesn't already exist.
        cursor.execute("SELECT 1 FROM %s" % table_name)

        # Above statement would have thrown a psycopg2.ProgrammingError if the
        # table didn't exist, but it didn't, so assume the table doesn't need to
        # be added.
        return
    except psycopg2.ProgrammingError:
        db.rollback()

    cursor.execute(statement)
    db.commit()

create("externalusers", """

CREATE TABLE externalusers
  ( id SERIAL PRIMARY KEY,
    uid INTEGER REFERENCES users,
    provider VARCHAR(16) NOT NULL,
    account VARCHAR(256) NOT NULL,
    email VARCHAR(256),
    token VARCHAR(256),

    UNIQUE (provider, account) );

""")

create("oauthstates", """

CREATE TABLE oauthstates
  ( state VARCHAR(64) PRIMARY KEY,
    url TEXT,
    time TIMESTAMP NOT NULL DEFAULT NOW() );

""")

db.commit()
db.close()
