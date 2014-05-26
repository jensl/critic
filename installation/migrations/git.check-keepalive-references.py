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
cursor.execute("""SELECT repositories.path, reviews.id, branches.id, branches.name, commits.sha1
                    FROM repositories
                    JOIN branches ON (branches.repository=repositories.id)
                    JOIN reviews ON (reviews.branch=branches.id)
                    JOIN commits ON (commits.id=branches.head)
                ORDER BY repositories.id, reviews.id""")

current_repository_path = None
keepalive_refs = None
branch_heads = None

sys.stdout.write("Verifying keepalive references ...\n")
sys.stdout.flush()

for repository_path, review_id, branch_id, branch_name, head_sha1 in cursor.fetchall():
    if repository_path != current_repository_path:
        keepalive_refs = set(subprocess.check_output(
            [data["installation.prereqs.git"],
             "--git-dir=" + repository_path,
             "for-each-ref", "--format=%(objectname)",
             "refs/keepalive/"]).splitlines())
        branch_heads = dict(
            line.rsplit(":", 1) for line in
            subprocess.check_output(
                [data["installation.prereqs.git"],
                 "--git-dir=" + repository_path,
                 "for-each-ref", "--format=%(refname):%(objectname)",
                 "refs/heads/"]).splitlines())

        current_repository_path = repository_path

        sys.stdout.write("\r\x1b[K  %s\n" % current_repository_path)

    sys.stdout.write("\r\x1b[K    r/%d" % review_id)
    sys.stdout.flush()

    def add_keepalive(sha1, message):
        keepalive_refs.add(sha1)

        try:
            subprocess.check_output(
                [data["installation.prereqs.git"],
                 "--git-dir=" + repository_path,
                 "update-ref", "refs/keepalive/" + sha1, sha1, "0" * 40],
                stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            what = "failed to add"
        else:
            what = "added"

        sys.stdout.write("\r\x1b[Kr/%d: %s keepalive ref: %s (%s)\n"
                         % (review_id, what, sha1, message))
        sys.stdout.flush()

    ####################################################################
    # Make sure the review branch in the Git repository references the #
    # expected commit, or that the commit it ought to reference is at  #
    # least kept alive.                                                #
    ####################################################################

    if branch_heads.get("refs/heads/" + branch_name) != head_sha1:
        if head_sha1 not in keepalive_refs:
            if "refs/heads/" + branch_name not in branch_heads:
                message = "missing review branch"
            else:
                message = "incorrect review branch"
            add_keepalive(head_sha1, message)

    ####################################################################
    # Make sure all "old head" commits from all past rebases of the    #
    # review are properly referenced by a keepalive ref.               #
    ####################################################################

    cursor.execute("""SELECT commits.id, commits.sha1
                        FROM commits
                        JOIN reviewrebases ON (reviewrebases.old_head=commits.id)
                       WHERE reviewrebases.review=%s
                         AND reviewrebases.new_head IS NOT NULL""",
                   (review_id,))

    for old_head_id, old_head_sha1 in cursor.fetchall():
        if old_head_sha1 not in keepalive_refs:
            # There might exist an "equivalent merge commit" that has
            # the recorded old head commit as one of its parent, and
            # that is kept alive.  Normally, that merge commit would be
            # recorded as the old head instead, but in old reviews this
            # is not the case if the merge was "clean".
            cursor.execute("""SELECT commits.sha1
                                FROM commits
                                JOIN edges ON (edges.child=commits.id)
                               WHERE edges.parent=%s""",
                           (old_head_id,))
            for candidate_sha1, in cursor:
                if candidate_sha1 in keepalive_refs:
                    # Note: Won't bother verifying that this actually is
                    # an equivalent merge commit, and not some random
                    # other commit with our old head as its parent.  If
                    # it's kept alive it's kept alive.
                    break
            else:
                add_keepalive(old_head_sha1, "rebase old head")

sys.stdout.write("\r\x1b[K")
sys.stdout.flush()
