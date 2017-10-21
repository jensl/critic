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
import shutil

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
    # Check if the 'relay' column already doesn't exist (and also fetch all the
    # relay paths for use below.)
    cursor.execute("SELECT relay FROM repositories")
except psycopg2.ProgrammingError:
    # Seems it doesn't exist, so just exit.
    sys.exit(0)

failed = False

for (relay_path,) in cursor:
    try:
        shutil.rmtree(relay_path)
    except OSError as error:
        print(("WARNING: Failed to remove directory: %s\n  Error: %s"
               % (relay_path, error)))
        failed = True

if failed:
    print("""
Some obsolete directories could not be removed.  They will no longer be used by
Critic, so you probably want to look into deleting them manually.
""")

cursor.execute("ALTER TABLE repositories DROP relay")

db.commit()
db.close()
