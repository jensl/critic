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

import re
import os
import signal

import dbutils
import gitutils
import htmlutils
import configuration

from operation import Operation, OperationResult, OperationError, Optional, OperationFailure
from reviewing.utils import parseReviewFilters, parseRecipientFilters, createReview, getReviewersAndWatchers
from page.createreview import generateReviewersAndWatchersTable
from log.commitset import CommitSet

if configuration.extensions.ENABLED:
    from extensions import executeProcessCommits

from cStringIO import StringIO

class ReviewersAndWatchers(Operation):
    def __init__(self):
        Operation.__init__(self, { "repository_id": int,
                                   "commit_ids": [int],
                                   "reviewfilters": [{ "username": str,
                                                       "type": set(["reviewer", "watcher"]),
                                                       "path": str }],
                                   "applyfilters": bool,
                                   "applyparentfilters": bool })

    def process(req, db, user, repository_id, commit_ids, reviewfilters, applyfilters, applyparentfilters):
        reviewfilters = parseReviewFilters(db, reviewfilters)

        repository = gitutils.Repository.fromId(db, repository_id)
        commits = [gitutils.Commit.fromId(db, repository, commit_id) for commit_id in commit_ids]

        all_reviewers, all_watchers = getReviewersAndWatchers(db, repository, commits,
                                                              reviewfilters=reviewfilters,
                                                              applyfilters=applyfilters,
                                                              applyparentfilters=applyparentfilters)
        document = htmlutils.Document(req)

        generateReviewersAndWatchersTable(db, repository, document,
                                          all_reviewers, all_watchers,
                                          applyfilters=applyfilters,
                                          applyparentfilters=applyparentfilters)

        return OperationResult(html=document.render(plain=True))

class SubmitReview(Operation):
    def __init__(self):
        Operation.__init__(self, { "repository_id": int,
                                   "commit_ids": [int],
                                   "branch": str,
                                   "summary": str,
                                   "applyfilters": bool,
                                   "applyparentfilters": bool,
                                   "reviewfilters": [{ "username": str,
                                                       "type": set(["reviewer", "watcher"]),
                                                       "path": str }],
                                   "recipientfilters": { "mode": set(["opt-in", "opt-out"]),
                                                         "included": Optional([str]),
                                                         "excluded": Optional([str]) },
                                   "description": Optional(str),
                                   "frombranch": Optional(str),
                                   "trackedbranch": Optional({ "remote": str,
                                                               "name": str }) })

    def process(self, db, user, repository_id, commit_ids, branch, summary,
                reviewfilters, recipientfilters, applyfilters, applyparentfilters,
                description=None, frombranch=None, trackedbranch=None):
        if not branch.startswith("r/"):
            raise OperationFailure(code="invalidbranch",
                                   title="Invalid review branch name",
                                   message="'%s' is not a valid review branch name; it must have a \"r/\" prefix." % branch)

        repository = gitutils.Repository.fromId(db, repository_id)

        components = branch.split("/")
        for index in range(1, len(components)):
            try: repository.revparse("refs/heads/%s" % "/".join(components[:index]))
            except gitutils.GitError: continue

            message = ("Cannot create branch with name<pre>%s</pre>since there is already a branch named<pre>%s</pre>in the repository." %
                       (htmlutils.htmlify(branch), htmlutils.htmlify("/".join(components[:index]))))
            raise OperationFailure(code="invalidbranch",
                                   title="Invalid review branch name",
                                   message=message,
                                   is_html=True)

        commits = [gitutils.Commit.fromId(db, repository, commit_id) for commit_id in commit_ids]
        commitset = CommitSet(commits)

        reviewfilters = parseReviewFilters(db, reviewfilters)
        recipientfilters = parseRecipientFilters(db, recipientfilters)

        review = createReview(db, user, repository, commits, branch, summary, description,
                              from_branch_name=frombranch,
                              reviewfilters=reviewfilters,
                              recipientfilters=recipientfilters,
                              applyfilters=applyfilters,
                              applyparentfilters=applyparentfilters)

        extensions_output = StringIO()
        kwargs = {}

        if configuration.extensions.ENABLED:
            if executeProcessCommits(db, user, review, commits, None, commitset.getHeads().pop(), extensions_output):
                kwargs["extensions_output"] = extensions_output.getvalue().lstrip()

        if trackedbranch:
            cursor = db.cursor()
            cursor.execute("""INSERT INTO trackedbranches (repository, local_name, remote, remote_name, forced, delay)
                                   VALUES (%s, %s, %s, %s, false, '1 hour')
                                RETURNING id""",
                           (repository_id, branch, trackedbranch["remote"], trackedbranch["name"]))

            trackedbranch_id = cursor.fetchone()[0]

            cursor.execute("""INSERT INTO trackedbranchusers (branch, uid)
                                   VALUES (%s, %s)""",
                           (trackedbranch_id, user.id))

            db.commit()

            pid = int(open(configuration.services.BRANCHTRACKER["pidfile_path"]).read().strip())
            os.kill(pid, signal.SIGHUP)

        return OperationResult(review_id=review.id, **kwargs)

class FetchRemoteBranches(Operation):
    def __init__(self):
        Operation.__init__(self, { "remote": str,
                                   "pattern": Optional(str) },
                           accept_anonymous_user=True)

    def process(self, db, user, remote, pattern=None):
        if pattern: regexp = re.compile(pattern.replace("*", ".*"))
        else: regexp = None

        try:
            refs = gitutils.Repository.lsremote(remote, regexp=regexp)
        except gitutils.GitCommandError, error:
            if error.output.splitlines()[0].endswith("does not appear to be a git repository"):
                raise OperationFailure(
                    code="invalidremote",
                    title="Invalid remote!",
                    message=("<code>%s</code> does not appear to be a valid Git repository."
                             % htmlutils.htmlify(remote)),
                    is_html=True)
            else:
                raise
        else:
            branches = dict([(ref[1], ref[0]) for ref in refs])
            return OperationResult(branches=branches)

class FetchRemoteBranch(Operation):
    def __init__(self):
        Operation.__init__(self, { "repository_name": str,
                                   "remote": str,
                                   "branch": str,
                                   "upstream": Optional(str) },
                           accept_anonymous_user=True)

    def process(self, db, user, repository_name, remote, branch, upstream="refs/heads/master"):
        repository = gitutils.Repository.fromName(db, repository_name)

        if not branch.startswith("refs/"):
            branch = "refs/heads/%s" % branch

        try:
            head_sha1 = repository.fetchTemporaryFromRemote(remote, branch)
        except gitutils.GitError:
            raise OperationFailure(
                code="refnotfound",
                title="Remote ref not found!",
                message=("Could not find the ref <code>%s</code> in the repository <code>%s</code>."
                         % (htmlutils.htmlify(branch), htmlutils.htmlify(remote))),
                is_html=True)
        except gitutils.GitCommandError, error:
            if error.output.splitlines()[0].endswith("does not appear to be a git repository"):
                raise OperationFailure(
                    code="invalidremote",
                    title="Invalid remote!",
                    message=("<code>%s</code> does not appear to be a valid Git repository."
                             % htmlutils.htmlify(remote)),
                    is_html=True)
            else:
                raise

        if upstream.startswith("refs/"):
            upstream_sha1 = repository.fetchTemporaryFromRemote(remote, upstream)
        else:
            upstream_sha1 = repository.revparse(upstream)

        commit_sha1s = repository.revlist(included=[head_sha1], excluded=[upstream_sha1])

        cursor = db.cursor()
        cursor.execute("SELECT id FROM commits WHERE sha1=ANY (%s)", (commit_sha1s,))

        return OperationResult(commit_ids=[commit_id for (commit_id,) in cursor],
                               head_sha1=head_sha1, upstream_sha1=upstream_sha1)
