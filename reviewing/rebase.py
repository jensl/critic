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
