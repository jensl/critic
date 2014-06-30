# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 Jens Lindström, Opera Software ASA
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
import subprocess

OLD_KEEPALIVE_REF_CHAIN = "refs/keepalive-chain"
NEW_KEEPALIVE_REF_CHAIN = "refs/internal/keepalive-chain"

parser = argparse.ArgumentParser()
parser.add_argument("--uid", type=int)
parser.add_argument("--gid", type=int)

arguments = parser.parse_args()

os.setgid(arguments.gid)
os.setuid(arguments.uid)

data = json.load(sys.stdin)

os.environ["HOME"] = data["installation.paths.data_dir"]
os.chdir(os.environ["HOME"])

db = psycopg2.connect(database="critic")
cursor = db.cursor()

cursor.execute("SELECT path FROM repositories")

for (path,) in cursor:
    try:
        # Create the new keepalive chain ref.
        subprocess.check_output(
            [data["installation.prereqs.git"],
             "--git-dir=%s" % path,
             "update-ref", NEW_KEEPALIVE_REF_CHAIN, OLD_KEEPALIVE_REF_CHAIN],
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        # Assume this was because OLD_KEEPALIVE_REF_CHAIN didn't exist.
        pass
    else:
        # Delete the old keepalive chain ref.  This command fails if the old
        # ref's value changed between this command and the previous one.
        subprocess.check_call(
            [data["installation.prereqs.git"],
             "--git-dir=%s" % path,
             "update-ref", "-d", OLD_KEEPALIVE_REF_CHAIN, NEW_KEEPALIVE_REF_CHAIN])
