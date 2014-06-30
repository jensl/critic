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

try:
    # Make sure the table doesn't already exist.
    cursor.execute("SELECT 1 FROM scheduledreviewbrancharchivals")

    # Above statement should have thrown a psycopg2.ProgrammingError, but it
    # didn't, so just exit.
    sys.exit(0)
except psycopg2.ProgrammingError: db.rollback()
except: raise

# Create the table.
cursor.execute("""

CREATE TABLE scheduledreviewbrancharchivals
  ( review INTEGER PRIMARY KEY REFERENCES reviews (id),
    deadline TIMESTAMP NOT NULL );

""")

# For each closed or dropped review, schedule an archival of the review branch.
# These archivals may end up being ignored, for instance because review branch
# archiving was disabled altogether.
#
# The archiving is randomly distributed over a four week period starting two
# weeks from now.
cursor.execute("""INSERT INTO scheduledreviewbrancharchivals (review, deadline)
                       SELECT id, NOW() + INTERVAL '2 weeks' + random() * INTERVAL '4 weeks'
                         FROM reviews
                        WHERE state IN ('closed', 'dropped')""")

db.commit()
db.close()
