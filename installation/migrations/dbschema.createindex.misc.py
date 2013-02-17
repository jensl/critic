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

parser = argparse.ArgumentParser()
parser.add_argument("--uid", type=int)
parser.add_argument("--gid", type=int)

arguments = parser.parse_args()

os.setgid(arguments.gid)
os.setuid(arguments.uid)

data = json.load(sys.stdin)

db = psycopg2.connect(database="critic")
cursor = db.cursor()

def create_index(table, columns):
    name = "%s_%s" % (table, "_".join(columns))
    cursor.execute("DROP INDEX IF EXISTS %s" % name)
    cursor.execute("CREATE INDEX %s ON %s (%s)" % (name, table, ", ".join(columns)))

# Replaced by index over 'uid' and 'state'.
cursor.execute("DROP INDEX IF EXISTS reviewfilechanges_uid")

create_index("reviewfiles", ["review", "state"])
create_index("reviewfilechanges", ["uid", "state"])
create_index("commentchains", ["review", "type", "state"])
create_index("comments", ["id", "chain"])

db.commit()
db.close()
