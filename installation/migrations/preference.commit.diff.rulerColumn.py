# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Rafał Chłodnicki, Opera Software ASA
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

db = psycopg2.connect(database="critic")
cursor = db.cursor()

# Make sure the preference doesn't already exist.
cursor.execute("SELECT 1 FROM preferences WHERE item=%s", ("commit.diff.rulerColumn",))

if cursor.fetchone():
    sys.exit(0)

cursor.execute("INSERT INTO preferences (item, type, default_integer, description) VALUES (%s, %s, %s, %s)",
               ("commit.diff.rulerColumn", "integer", 0,
                "The column at which a ruler is shown. Can be set to 0 to disable the ruler."))

db.commit()
db.close()
