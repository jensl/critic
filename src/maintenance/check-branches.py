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
import argparse
import errno

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import dbutils
import gitutils
import log.commitset
from . import progress

parser = argparse.ArgumentParser()
parser.add_argument("--exclude", action="append", help="exclude repository")
parser.add_argument("--include", action="append", help="include (only) repository")
parser.add_argument("--dry-run", "-n", action="store_true", help="don't touch the database or repositories")
parser.add_argument("--force", "-f", action="store_true", help="update the database and/or repositories")

arguments = parser.parse_args()

if not arguments.dry_run and not arguments.force:
    print("One of --dry-run/-n and --force/-f must be specified.")
    sys.exit(1)
elif arguments.dry_run and arguments.force:
    print("Only one of --dry-run/-n and --force/-f can be specified.")
    sys.exit(1)

force = arguments.force

db = dbutils.Database.forSystem()
cursor = db.cursor()

def getBranchCommits(repository, branch_id):
    cursor = db.cursor()
    cursor.execute("SELECT sha1 FROM commits JOIN reachable ON (commit=id) WHERE branch=%s", (branch_id,))

    return log.commitset.CommitSet(gitutils.Commit.fromSHA1(db, repository, sha1) for (sha1,) in cursor)

def getReview(branch_id):
    cursor = db.cursor()
    cursor.execute("SELECT id FROM reviews WHERE branch=%s", (branch_id,))
    return cursor.fetchone()[0]

def getReviewCommits(repository, review_id):
    review_id = getReview(branch_id)

    cursor.execute("""SELECT changesets.child
                        FROM changesets
                        JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                       WHERE reviewchangesets.review=%s""",
                   (review_id,))

    return log.commitset.CommitSet(gitutils.Commit.fromId(db, repository, commit_id) for (commit_id,) in cursor)

def getReviewHead(repository, review_id):
    commits = getReviewCommits(repository, review_id)
    heads = commits.getHeads()

    if len(heads) == 1: return heads.pop()

    cursor = db.cursor()
    cursor.execute("""SELECT commits.sha1
                        FROM commits
                        JOIN reviewrebases ON (reviewrebases.old_head=commits.id)
                       WHERE reviewrebases.review=%s""",
                   (review_id,))

    for (sha1,) in cursor: heads.remove(sha1)

    if len(heads) == 1: return heads.pop()
    else: return None

if arguments.include:
    cursor.execute("SELECT id FROM repositories WHERE name=ANY (%s)", (arguments.include,))
else:
    cursor.execute("SELECT id FROM repositories")
repository_ids = cursor.fetchall()

incorrect_reviews = []

for repository_id in repository_ids:
    repository = gitutils.Repository.fromId(db, repository_id)

    if arguments.exclude and repository.name in arguments.exclude:
        print("Repository: %s (skipped)" % repository.name)
        continue

    cursor.execute("""SELECT branches.id, branches.name, branches.type, branches.base, commits.sha1
                        FROM branches
                        JOIN commits ON (commits.id=branches.head)
                       WHERE branches.repository=%s""",
                   (repository_id,))

    branches = cursor.fetchall()
    refs = {}
    batch = []

    try:
        for line in open(os.path.join(repository.path, "packed-refs")):
            if not line.startswith("#"):
                try:
                    sha1, ref = line.split()
                    if len(sha1) == 40 and ref.startswith("refs/heads/"):
                        refs[ref[11:]] = sha1
                except ValueError:
                    pass
    except IOError as error:
        if error.errno == errno.ENOENT: pass
        else: raise

    progress.start(len(branches), "Repository: %s" % repository.name)

    heads_path = os.path.join(repository.path, "refs", "heads")

    branches_in_db = set()

    for branch_id, branch_name, branch_type, branch_base_id, branch_sha1 in branches:
        progress.update()

        branches_in_db.add(branch_name)

        try:
            try: repository_sha1 = open(os.path.join(heads_path, branch_name)).read().strip()
            except: repository_sha1 = refs.get(branch_name)

            if repository_sha1 != branch_sha1:
                progress.write("NOTE[%s]: %s differs (db:%s != repo:%s)" % (repository.name, branch_name, branch_sha1[:8], repository_sha1[:8]))

                if branch_type == "review":
                    head = getReviewHead(repository, getReview(branch_id))

                    if not head:
                        progress.write("  invalid review meta-data: r/%d" % getReview(branch_id))
                        continue

                    if head.sha1 == branch_sha1:
                        progress.write("  branches.head matches review meta-data; repository is wrong")
                        if force: repository.run("update-ref", "refs/heads/%s" % branch_name, head.sha1, repository_sha1)
                        progress.write("  repository updated")
                    elif head.sha1 == repository_sha1:
                        progress.write("  repository matches review meta-data; branches.head is wrong")
                        if force: cursor.execute("UPDATE branches SET head=%s WHERE id=%s", (head.getId(db), branch_id))
                        db.commit()
                    else:
                        progress.write("  review meta-data matches neither branches.head nor repository")
                        incorrect_reviews.append((getReview(branch_id), "review meta-data matches neither branches.head nor repository"))
                else:
                    try:
                        gitutils.Commit.fromSHA1(db, repository, branch_sha1)
                        progress.write("  branches.head exists in repository")
                    except KeyboardInterrupt: sys.exit(1)
                    except:
                        progress.write("  branches.head not in repository; updating branches.head")
                        head = gitutils.Commit.fromSHA1(db, repository, repository_sha1)
                        if force: cursor.execute("UPDATE branches SET head=%s WHERE id=%s", (head.getId(db), branch_id))
                        db.commit()
                        continue

                    try:
                        commits = getBranchCommits(repository, branch_id)
                        heads = commits.getHeads()

                        if len(heads) > 1:
                            progress.write("  reachable commit-set has multiple heads")
                            continue

                        head = heads.pop()

                        if head.sha1 == branch_sha1:
                            progress.write("  reachable agrees with branches.head; repository is wrong")
                            if force: repository.run("update-ref", "refs/heads/%s" % branch_name, head.sha1, repository_sha1)
                            progress.write("  repository updated")
                        elif head.sha1 == repository_sha1:
                            progress.write("  reachable agrees with repository; branches.head is wrong")
                            if force: cursor.execute("UPDATE branches SET head=%s WHERE id=%s", (head.getId(db), branch_id))
                            db.commit()
                            continue
                    except KeyboardInterrupt: sys.exit(1)
                    except:
                        progress.write("  reachable contains missing commits")
        except KeyboardInterrupt: sys.exit(1)
        except:
            progress.write("WARNING[%s]: %s missing!" % (repository.name, branch_name))

            if branch_type == "normal":
                cursor.execute("SELECT id FROM branches WHERE base=%s", (branch_id,))

                sub_branches = cursor.fetchall()
                if sub_branches:
                    progress.write("  branch has sub-branches")

                    base_branch = dbutils.Branch.fromId(db, branch_base_id)

                    for (sub_branch_id,) in sub_branches:
                        sub_branch = dbutils.Branch.fromId(db, sub_branch_id)
                        sub_branch.rebase(db, base_branch)
                        progress.write("    rebased sub-branch %s" % sub_branch.name)

                try:
                    if force:
                        cursor.execute("DELETE FROM branches WHERE id=%s", (branch_id,))
                        db.commit()
                    progress.write("  deleted from database")
                except KeyboardInterrupt: sys.exit(1)
                except:
                    progress.write("  failed to delete from database")
                    db.rollback()
            else:
                try: review_id = getReview(branch_id)
                except KeyboardInterrupt: sys.exit(1)
                except:
                    progress.write("  review branch without review; deleting")
                    try:
                        if force: cursor.execute("DELETE FROM branches WHERE id=%s", (branch_id,))
                        db.commit()
                    except KeyboardInterrupt: sys.exit(1)
                    except:
                        progress.write("  failed to delete from database")
                        db.rollback()
                    continue

                try: commits = getReviewCommits(repository, getReview(branch_id))
                except KeyboardInterrupt: sys.exit(1)
                except:
                    progress.write("  review meta-data references missing commits")
                    incorrect_reviews.append((getReview(branch_id), "branches.head = %s" % branch_sha1))
                    continue

                heads = commits.getHeads()

                if len(heads) > 1:
                    progress.write("  multiple heads: r/%d" % review_id)
                    continue

                head = heads.pop()

                try:
                    if force: repository.run("update-ref", "refs/heads/%s" % branch_name, head.sha1, "0" * 40)
                    progress.write("  re-created review branch")
                except KeyboardInterrupt: sys.exit(1)
                except:
                    progress.write("  failed to re-create review branch")
                    incorrect_reviews.append((getReview(branch_id), "failed to re-create review branch"))

    processed = set()

    def exists_in_db(branch_name):
        return branch_name in branches_in_db

    def process(path, prefix=None):
        for entry in os.listdir(path):
            entry_path = os.path.join(path, entry)
            branch_name = os.path.join(prefix, entry) if prefix else entry
            if os.path.isdir(entry_path):
                process(entry_path, branch_name)
            elif not exists_in_db(branch_name):
                progress.write("WARNING[%s]: %s exists in the repository but not in the database!" % (repository.name, branch_name))
                if force: repository.run("update-ref", "-d", "refs/heads/%s" % branch_name)
                progress.write("  deleted from repository")
            processed.add(branch_name)

    for branch_name in refs.keys():
        if branch_name not in processed and not exists_in_db(branch_name):
            progress.write("WARNING[%s]: %s exists in the repository but not in the database!" % (repository.name, branch_name))
            if force: repository.run("update-ref", "-d", "refs/heads/%s" % branch_name)
            progress.write("  deleted from repository")

    process(heads_path)

    progress.end(".")

if incorrect_reviews:
    print("\nReviews that need attention:")

    for review_id, message in incorrect_reviews:
        print("  %5d: %s" % (review_id, message))
