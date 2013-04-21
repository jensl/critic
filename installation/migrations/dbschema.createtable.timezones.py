# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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
import datetime

parser = argparse.ArgumentParser()
parser.add_argument("--uid", type=int)
parser.add_argument("--gid", type=int)

arguments = parser.parse_args()

os.setgid(arguments.gid)
os.setuid(arguments.uid)

data = json.load(sys.stdin)

db = psycopg2.connect(database="critic")
cursor = db.cursor()

try:
    # Make sure the table doesn't already exist.
    cursor.execute("SELECT 1 FROM timezones")

    # Above statement should have thrown a psycopg2.ProgrammingError, but it
    # didn't, so just exit.
    sys.exit(0)
except psycopg2.ProgrammingError:
    db.rollback()

cursor.execute("""CREATE TABLE timezones
                    ( name VARCHAR(256) PRIMARY KEY,
                      abbrev VARCHAR(16) NOT NULL,
                      utc_offset INTERVAL NOT NULL )""")

# Additional timezones are copied from 'pg_timezone_names' by the Watchdog
# service on startup.

cursor.execute("INSERT INTO timezones (name, abbrev, utc_offset) VALUES (%s, %s, %s)",
               ("Universal/UTC", "UTC", datetime.timedelta()))

db.commit()
db.close()
