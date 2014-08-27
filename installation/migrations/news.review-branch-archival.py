# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 Jens Widell, Opera Software ASA
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
Review branch archival
======================

This Critic system now supports automatic archival of obsolete review branches.
This means that review branch refs that belong to reviews that are finished and
closed, or dropped, are eventually deleted from the repository.

For more information, see the [Review branch archival][tutorial]
tutorial.

From now on, archival of review branches is scheduled when reviews are closed or
dropped.  For each existing already closed or dropped reviews in this system,
archival will have been scheduled at a random time 2-6 weeks after the upgrade.
This news item's timestamp indicates when the upgrade took place.

[tutorial]: /tutorial?item=archival
"""

cursor.execute("SELECT id FROM newsitems WHERE text=%s", (text,))

if cursor.fetchone():
    # Identical news item already exists.
    sys.exit(0)

cursor.execute("INSERT INTO newsitems (text) VALUES (%s)", (text,))

db.commit()
db.close()

# Also print a "news" bulletin to the system administrator that
# performs the upgrade:

print """
NOTE: This update adds a review branch archival mechanism, enabled by
      default.  To find out more about it, including how to disable
      it, please see the administration tutorial:

  http://<this-system>/tutorial?item=administration#review_branch_archival
"""
