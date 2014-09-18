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
import argparse
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--uid", type=int)
parser.add_argument("--gid", type=int)

arguments = parser.parse_args()

os.setgid(arguments.gid)
os.setuid(arguments.uid)

import configuration

db = psycopg2.connect(**configuration.database.PARAMETERS)
cursor = db.cursor()

try:
    # Check if the 'replayed_rebase' column already exists.
    cursor.execute("SELECT replayed_rebase FROM reviewrebases")
except psycopg2.ProgrammingError:
    db.rollback()
else:
    # No error; change appears to have been made already.
    db.close()
    sys.exit(0)

cursor.execute("""ALTER TABLE reviewrebases
                          ADD replayed_rebase INTEGER REFERENCES commits""")

#
# Find all replayed rebases and store them in the new |replayed_rebase| column.
# We identify them via 'conflicts' changesets added for review, whose child
# (right-hand side) is the new head of a rebase.  The parent (left-hand side) of
# such a changeset will be the replayed rebase commit.
#
# Note: It is theoretically possible for such a 'conflicts' changeset to exist
# that is not actually indicative of a replayed rebase, if the rebase's new head
# is a merge commit, and that merge commit is an equivalent merge commit created
# for an earlier rebase of the same review.
#
# Also note: While theoretically possible, the aforementioned possibility is not
# likely to have happened in practice.
#

cursor.execute("""SELECT DISTINCT changesets.parent, reviewrebases.id
                    FROM reviewrebases
                    JOIN reviewchangesets ON (reviewchangesets.review=reviewrebases.review)
                    JOIN changesets ON (changesets.id=reviewchangesets.changeset
                                    AND changesets.child=reviewrebases.new_head)
                   WHERE changesets.type='conflicts'""")

cursor.executemany("""UPDATE reviewrebases
                         SET replayed_rebase=%s
                       WHERE id=%s""",
                   cursor.fetchall())

db.commit()
db.close()
