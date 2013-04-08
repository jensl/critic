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
    cursor.execute("CREATE INDEX reviewmessageids_review ON reviewmessageids (review)")
except psycopg2.ProgrammingError:
    # The index probably already exists.
    db.rollback()
else:
    db.commit()

cursor.execute("""ALTER TABLE branches
                    DROP CONSTRAINT IF EXISTS branches_review_fkey,
                    ADD CONSTRAINT branches_review_fkey
                      FOREIGN KEY (review) REFERENCES reviews ON DELETE CASCADE""")

cursor.execute("""ALTER TABLE checkbranchnotes
                    DROP CONSTRAINT IF EXISTS checkbranchnotes_review_fkey,
                    ADD CONSTRAINT checkbranchnotes_review_fkey
                      FOREIGN KEY (review) REFERENCES reviews ON DELETE CASCADE""")

db.commit()
db.close()
