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
import os
import os.path
import time
import cPickle

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import dbutils
import gitutils
import progress

db = dbutils.Database()
cursor = db.cursor()

commits = {}
pending_commits = set()

cursor.execute("SELECT COUNT(*) FROM commits")

print

progress.start(cursor.fetchone()[0], prefix="Fetching commits ...")

cursor.execute("SELECT id, sha1 FROM commits")

for commit_id, commit_sha1 in cursor:
    commits[commit_id] = commit_sha1
    pending_commits.add(commit_id)

    progress.update()

progress.end(" %d commits." % len(commits))

print

cursor.execute("SELECT MAX(CHARACTER_LENGTH(name)) FROM repositories")

repository_name_length = cursor.fetchone()[0]

cursor.execute("SELECT id FROM repositories ORDER BY id ASC")

repositories = [repository_id for (repository_id,) in cursor]

def processCommits(process_commits):
    global commits

    processed_commits = set()

    current = 0
    total = len(process_commits)

    for commit_id in process_commits:
        try:
            gitobject = repository.fetch(commits[commit_id])
            if gitobject.type == "commit": processed_commits.add(commit_id)
        except gitutils.GitError:
            pass
        except KeyboardInterrupt:
            sys.exit(1)
        except:
            raise

        progress.update()

    return processed_commits

for repository_id in repositories:
    repository = gitutils.Repository.fromId(db, repository_id)
    repository.disableCache()

    cursor.execute("SELECT commit FROM reachable JOIN branches ON (branch=id) WHERE repository=%s", (repository.id,))
    process_commits = set(commit_id for (commit_id,) in cursor if commit_id in pending_commits)

    progress.start(len(process_commits), "Scanning repository: %-*s" % (repository_name_length, repository.name))

    processed_commits = processCommits(process_commits)

    missing = len(process_commits) - len(processed_commits)
    if missing:
        message = " %d commits found; %d commits missing!" % (len(processed_commits), missing)
    else:
        message = " %d commits found." % len(processed_commits)
    progress.end(message)

    pending_commits -= processed_commits

if pending_commits:
    print
    print "%d commits still unaccounted for.  Re-scanning all repositories." % len(pending_commits)
    print

    for repository_id in repositories:
        repository = gitutils.Repository.fromId(db, repository_id)
        repository.disableCache()

        progress.start(len(pending_commits), "Re-scanning repository: %-*s" % (repository_name_length, repository.name))

        processed_commits = processCommits(pending_commits)
        pending_commits -= processed_commits

        progress.end(" %d commits found, %d remaining." % (len(processed_commits), len(pending_commits)))

        if not pending_commits: break

    if pending_commits:
        cPickle.dump(pending_commits, open("commits-to-purge.pickle", "w"), 2)

        print
        print "%d commits that were not found in any repository should be purged." % len(pending_commits)
        print "Run purge-commits.py to do this."
