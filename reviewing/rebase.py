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

import time

import gitutils

def timestamp(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", ts)

def createEquivalentMergeCommit(db, review, user, old_head, old_upstream, new_head, new_upstream, onto_branch=None):
    repository = review.repository

    old_upstream_name = repository.findInterestingTag(db, old_upstream.sha1) or old_upstream.sha1
    new_upstream_name = repository.findInterestingTag(db, new_upstream.sha1) or new_upstream.sha1

    if onto_branch:
        merged_thing = "branch '%s'" % onto_branch
    else:
        merged_thing = "commit '%s'" % new_upstream_name

    commit_message = """\
Merge %(merged_thing)s into %(review.branch.name)s

This commit was generated automatically by Critic as an equivalent merge
to the rebase of the commits

  %(old_upstream_name)s..%(old_head.sha1)s

onto the %(merged_thing)s.""" % { "merged_thing": merged_thing,
                                  "review.branch.name": review.branch.name,
                                  "old_upstream_name": old_upstream_name,
                                  "old_head.sha1": old_head.sha1 }

    merge_sha1 = repository.run('commit-tree', new_head.tree, '-p', old_head.sha1, '-p', new_upstream.sha1,
                                input=commit_message,
                                env={ 'GIT_AUTHOR_NAME': user.fullname,
                                      'GIT_AUTHOR_EMAIL': user.email,
                                      'GIT_COMMITTER_NAME': user.fullname,
                                      'GIT_COMMITTER_EMAIL': user.email }).strip()

    merge = gitutils.Commit.fromSHA1(db, repository, merge_sha1)
    gituser_id = merge.author.getGitUserId(db)

    cursor = db.cursor()
    cursor.execute("""INSERT INTO commits (sha1, author_gituser, commit_gituser, author_time, commit_time)
                           VALUES (%s, %s, %s, %s, %s)
                        RETURNING id""",
                   (merge.sha1, gituser_id, gituser_id, timestamp(merge.author.time), timestamp(merge.committer.time)))
    merge.id = cursor.fetchone()[0]

    cursor.executemany("INSERT INTO edges (parent, child) VALUES (%s, %s)",
                       [(old_head.getId(db), merge.id),
                        (new_upstream.getId(db), merge.id)])

    # Need to commit the transaction to make the new commit available
    # to other database sessions right away, specifically so that the
    # changeset service can see it.
    db.commit()

    return merge

def replayRebase(db, review, user, old_head, old_upstream, new_head, new_upstream, onto_branch=None):
    repository = review.repository

    old_upstream_name = repository.findInterestingTag(db, old_upstream.sha1) or old_upstream.sha1

    if onto_branch:
        new_upstream_name = "branch '%s'" % onto_branch
    else:
        new_upstream_name = "commit '%s'" % (repository.findInterestingTag(db, new_upstream.sha1) or new_upstream.sha1)

    commit_message = """\
Rebased %(review.branch.name)s onto %(new_upstream_name)s

This commit was generated automatically by Critic to "replay" the
rebase of the commits

  %(old_upstream_name)s..%(old_head.sha1)s

onto the %(new_upstream_name)s.""" % { "review.branch.name": review.branch.name,
                                       "old_head.sha1": old_head.sha1,
                                       "old_upstream_name": old_upstream_name,
                                       "new_upstream_name": new_upstream_name }

    original_sha1 = repository.run('commit-tree', old_head.tree, '-p', old_upstream.sha1,
                                   input=commit_message,
                                   env={ 'GIT_AUTHOR_NAME': user.fullname,
                                         'GIT_AUTHOR_EMAIL': user.email,
                                         'GIT_COMMITTER_NAME': user.fullname,
                                         'GIT_COMMITTER_EMAIL': user.email }).strip()

    repository.run("update-ref", "refs/commit/%s" % new_upstream.sha1, new_upstream.sha1)
    repository.run("update-ref", "refs/commit/%s" % original_sha1, original_sha1)

    with repository.workcopy(original_sha1) as workcopy:
        workcopy.run("fetch", "--quiet", "origin",
                     "refs/commit/%s:refs/heads/temporary" % new_upstream.sha1,
                     "refs/commit/%s:refs/heads/original" % original_sha1)

        workcopy.run("checkout", "temporary")

        returncode, stdout, stderr = workcopy.run("cherry-pick", "refs/heads/original", check_errors=False)

        # If the rebase produced conflicts, just stage and commit them:
        if returncode != 0:
            # Reset any submodule gitlinks with conflicts: since we don't
            # have the submodules checked out, "git commit --all" below
            # may fail to index them.
            for line in stdout.splitlines():
                if line.startswith("CONFLICT (submodule):"):
                    submodule_path = line.split()[-1]
                    workcopy.run("reset", "--", submodule_path, check_errors=False)

            # Then stage and commit the result, with conflict markers and all.
            workcopy.run("commit", "--all", "--reuse-message=%s" % original_sha1)

        rebased_sha1 = workcopy.run("rev-parse", "HEAD").strip()

        workcopy.run("push", "origin", "HEAD:refs/keepalive/%s" % rebased_sha1)

    return gitutils.Commit.fromSHA1(db, repository, rebased_sha1)
