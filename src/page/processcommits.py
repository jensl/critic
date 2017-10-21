# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import io

import extensions
import gitutils
import log.commitset
import page.utils

def renderProcessCommits(req, db, user):
    review_id = req.getParameter("review", filter=int)
    commit_ids = list(map(int, req.getParameter("commits").split(",")))

    review = dbutils.Review.fromId(db, review_id)
    all_commits = [gitutils.Commit.fromId(db, review.repository, commit_id) for commit_id in commit_ids]
    commitset = log.commitset.CommitSet(all_commits)

    heads = commitset.getHeads()
    tails = commitset.getTails()

    def process():
        if len(heads) != 1:
            return "invalid commit-set; multiple heads"
        if len(tails) != 1:
            return "invalid commit-set; multiple tails"

        old_head = gitutils.Commit.fromSHA1(db, review.repository, tails.pop())
        new_head = heads.pop()

        output = io.StringIO()

        extensions.role.processcommits.execute(db, user, review, all_commits, old_head, new_head, output)

        return output.getvalue()

    return page.utils.ResponseBody(process(), content_type="text/plain")
