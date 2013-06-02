# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Martin Olsson
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

try:
    # Check if the 'installed_sha1' column already exists.
    cursor.execute("SELECT installed_sha1 FROM systemidentities")
except psycopg2.ProgrammingError:
    db.rollback()
    cursor.execute("ALTER TABLE systemidentities ADD installed_sha1 CHAR(40)")
    cursor.execute("UPDATE systemidentities SET installed_sha1=''")
    cursor.execute("ALTER TABLE systemidentities ALTER installed_sha1 SET NOT NULL")
    db.commit()

try:
    # Check if the 'installed_at' column already exists.
    cursor.execute("SELECT installed_at FROM systemidentities")
except psycopg2.ProgrammingError:
    db.rollback()
    cursor.execute("ALTER TABLE systemidentities ADD installed_at TIMESTAMP DEFAULT NOW()")
    cursor.execute("ALTER TABLE systemidentities ALTER installed_at SET NOT NULL")
    db.commit()

db.close()
