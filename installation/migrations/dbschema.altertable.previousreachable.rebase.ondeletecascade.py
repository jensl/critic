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

# This command doesn't fail if the foreign key constraint already has
# "on delete cascade", and there's really no reason to try to figure
# if it has; easier to just drop it and re-add it.
cursor.execute("""ALTER TABLE previousreachable
                    DROP CONSTRAINT previousreachable_rebase_fkey,
                    ADD FOREIGN KEY (rebase) REFERENCES reviewrebases (id) ON DELETE CASCADE""")

db.commit()
db.close()
