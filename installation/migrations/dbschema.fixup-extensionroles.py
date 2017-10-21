# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 Jens Lindström, Opera Software ASA
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

try:
    # The extensions part of the database schema might not have been loaded at
    # all; it isn't until extend.py is used to enable extensions support.
    cursor.execute("SELECT 1 FROM extensions")
except psycopg2.ProgrammingError:
    sys.exit(0)

cursor.execute("""SELECT id, version, script, function,
                         extensionpageroles.path,
                         extensioninjectroles.path,
                         extensionprocesscommitsroles.role IS NULL
                    FROM extensionroles
         LEFT OUTER JOIN extensionpageroles
                      ON (extensionpageroles.role=id)
         LEFT OUTER JOIN extensioninjectroles
                      ON (extensioninjectroles.role=id)
         LEFT OUTER JOIN extensionprocesscommitsroles
                      ON (extensionprocesscommitsroles.role=id)""")

roles = set()
duplicates = []

for row in cursor:
    role_id = row[0]
    role_key = row[1:]

    if role_key in roles:
        duplicates.append(role_id)
    else:
        roles.add(role_key)

if duplicates:
    print("Removing %d duplicate rows from extensionroles." % len(duplicates))
    cursor.execute("DELETE FROM extensionroles WHERE id=ANY (%s)", (duplicates,))

db.commit()
db.close()
