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
    cursor.execute("SELECT key, url_prefix FROM systemidentities")
except psycopg2.ProgrammingError:
    # We seem to have converted the table already, so just exit.
    sys.exit(0)

url_prefixes = cursor.fetchall()

cursor.execute("""ALTER TABLE systemidentities
                      DROP url_prefix,
                      ADD anonymous_scheme VARCHAR(5),
                      ADD authenticated_scheme VARCHAR(5),
                      ADD hostname VARCHAR(256)""")

if configuration.base.ACCESS_SCHEME in ("http", "https"):
    anonymous_scheme = authenticated_scheme = configuration.base.ACCESS_SCHEME
else:
    anonymous_scheme = "http"
    authenticated_scheme = "https"

for key, url_prefix in url_prefixes:
    if url_prefix.lower().startswith("https://"):
        hostname = url_prefix[len("https://"):]
    elif url_prefix.lower().startswith("http://"):
        hostname = url_prefix[len("http://"):]
    else:
        # This would only happen if the system administrator manually
        # modified the 'systemidentities' table, and any URL constructed
        # with this URL prefix in the past would most likely have been
        # broken already.

        print """\
WARNING: System identity %s's URL prefix was not recognized as either
         HTTP or HTTPS.  It's assumed to be a plain hostname.

The URL prefix was: %r""" % (key, url_prefix)

        hostname = url_prefix

    cursor.execute("""UPDATE systemidentities
                         SET anonymous_scheme=%s,
                             authenticated_scheme=%s,
                             hostname=%s
                       WHERE key=%s""",
                   (anonymous_scheme, authenticated_scheme, hostname, key))

cursor.execute("""ALTER TABLE systemidentities
                      ALTER anonymous_scheme SET NOT NULL,
                      ALTER authenticated_scheme SET NOT NULL,
                      ALTER hostname SET NOT NULL""")

db.commit()
db.close()
