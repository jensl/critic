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
Review Quick Search
===================

Critic's mechanism for searching for reviews has been upgraded.  The existing
  <a href=/search>search page</a>
has been made somewhat more user-friendly and capable.

More significantly, a new "quick search" feature has been added, which is a
search dialog activated by pressing the <code>F</code> key on any Critic page
(for instance this one.)  This dialog allows input of a search query and can be
used to perform the same searches as the main search page.

For more details, see the (new)
  <a href='/tutorial?item=search'>tutorial on the subject of searching</a>."""

cursor.execute("SELECT id FROM newsitems WHERE text=%s", (text,))

if cursor.fetchone():
    # Identical news item already exists.
    sys.exit(0)

cursor.execute("INSERT INTO newsitems (text) VALUES (%s)", (text,))

db.commit()
db.close()
