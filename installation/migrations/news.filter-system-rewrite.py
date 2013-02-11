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

text = """\
Improved Filters
================

Critic's Filters mechanism has been improved, in two significant ways:

* filter paths can now contain wildcards, and
* a third filter type, <b>Ignored</b>, has been added, that can be
  used to exclude some files or directories otherwise matched by other
  filters.

For more details, see the (new)
  <a href='/tutorial?item=filters'>tutorial on the subject of filters</a>.

The UI for managing filters on your
  <a href='/home'>Home page</a>
has also been significantly changed; now displaying all filter in all
repositories instead of only filters in a selected repository."""

cursor.execute("SELECT id FROM newsitems WHERE text=%s", (text,))

if cursor.fetchone():
    # Identical news item already exists.
    sys.exit(0)

cursor.execute("INSERT INTO newsitems (text) VALUES (%s)", (text,))

db.commit()
db.close()
