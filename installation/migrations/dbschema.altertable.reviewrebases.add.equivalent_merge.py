# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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
import subprocess

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
    # Check if the 'equivalent_merge' column already exists.
    cursor.execute("SELECT equivalent_merge FROM reviewrebases")
except psycopg2.ProgrammingError:
    db.rollback()
else:
    # No error; change appears to have been made already.
    db.close()
    sys.exit(0)

def fetch_commit_sha1(commit_id):
    cursor.execute("SELECT sha1 FROM commits WHERE id=%s", (commit_id,))
    (sha1,) = cursor.fetchone()
    return sha1

def get_parent_sha1s(repository_path, sha1):
    output = subprocess.check_output(
        [configuration.executables.GIT, "log", "-1", "--format=%P", sha1],
        cwd=repository_path)
    return output.strip().split()

def is_ancestor_of(repository_path, ancestor_sha1, descendant_sha1):
    try:
        merge_base_sha1 = subprocess.check_output(
            [configuration.executables.GIT, "merge-base",
             ancestor_sha1, descendant_sha1],
            cwd=repository_path).strip()
    except subprocess.CalledProcessError:
        return False
    else:
        return merge_base_sha1 == ancestor_sha1

cursor.execute("""ALTER TABLE reviewrebases
                          ADD equivalent_merge INTEGER REFERENCES commits""")

#
# Move all references to equivalent merges stored in the |old_head| column of
# existing review rebases over to the new |equivalent_merge| column, and restore
# the value of the |old_head| to be the actual head of the review branch before
# the rebase.
#

cursor.execute("""SELECT repositories.path,
                         reviewrebases.id,
                         reviewrebases.old_head,
                         reviewrebases.old_upstream,
                         reviewrebases.new_upstream
                    FROM reviewrebases
                    JOIN reviews ON (reviews.id=reviewrebases.review)
                    JOIN branches ON (branches.id=reviews.branch)
                    JOIN repositories ON (repositories.id=branches.repository)
                   WHERE new_head IS NOT NULL
                     AND old_upstream IS NOT NULL
                     AND new_upstream IS NOT NULL""")

for repository_path, rebase_id, old_head_id, old_upstream_id, new_upstream_id in cursor.fetchall():
    old_head_sha1 = fetch_commit_sha1(old_head_id)
    old_head_parent_sha1s = get_parent_sha1s(repository_path, old_head_sha1)

    if len(old_head_parent_sha1s) != 2:
        # Old head is not a merge commit (or is an 3-or-more-way merge,) so
        # can't be an equivalent merge.
        continue

    old_upstream_sha1 = fetch_commit_sha1(old_upstream_id)
    new_upstream_sha1 = fetch_commit_sha1(new_upstream_id)

    if old_head_parent_sha1s[1] != new_upstream_sha1:
        # An equivalent merge should be a merge with the real old head as the
        # first parent and the new upstream as the second parent.  We can't
        # really check the first parent in a meaningful way, but if the second
        # parent is "wrong", then this can't be an equivalent merge.
        continue

    if not is_ancestor_of(repository_path, old_upstream_sha1, new_upstream_sha1):
        # Old upstream is not an ancestor of the new upstream, meaning this is
        # not a "fast-forward" rebase.  Such rebases don't have an equivalent
        # merge, but rather a "replayed rebase".  The replayed rebase however
        # isn't stored in the |old_head| column, so there is nothing to restore.
        continue

    # Alright, we're pretty sure that the old head is in fact an equivalent
    # merge commit.  Store it in the new |equivalent_merge| column and restore
    # the |old_head| column to the equivalent merge's first parent.

    cursor.execute("SELECT id FROM commits WHERE sha1=%s",
                   (old_head_parent_sha1s[0],))
    (real_old_head_id,) = cursor.fetchone()

    cursor.execute("""UPDATE reviewrebases
                         SET old_head=%s,
                             equivalent_merge=%s
                       WHERE id=%s""",
                   (real_old_head_id, old_head_id, rebase_id))

db.commit()
db.close()
