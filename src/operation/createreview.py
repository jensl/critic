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

from operation import (Operation, OperationResult, OperationError, Optional,
                       OperationFailure, Repository)
from reviewing.utils import (parseReviewFilters, parseRecipientFilters,
                             createReview, getReviewersAndWatchers)
from page.createreview import generateReviewersAndWatchersTable
from log.commitset import CommitSet

if configuration.extensions.ENABLED:
    import extensions.role.processcommits

from io import StringIO

class ReviewersAndWatchers(Operation):
    def __init__(self):
        Operation.__init__(self, { "repository_id": int,
                                   "commit_ids": [int],
                                   "reviewfilters": [{ "username": str,
                                                       "type": {"reviewer", "watcher"},
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
        Operation.__init__(self, { "repository": Repository,
                                   "branch": str,
                                   "summary": str,
                                   "commit_ids": Optional([int]),
                                   "commit_sha1s": Optional([str]),
                                   "applyfilters": Optional(bool),
                                   "applyparentfilters": Optional(bool),
                                   "reviewfilters": Optional([{ "username": str,
                                                                "type": {"reviewer", "watcher"},
                                                                "path": str }]),
                                   "recipientfilters": Optional({ "mode": {"opt-in", "opt-out"},
                                                                  "included": Optional([str]),
                                                                  "excluded": Optional([str]) }),
                                   "description": Optional(str),
                                   "frombranch": Optional(str),
                                   "trackedbranch": Optional({ "remote": str,
                                                               "name": str }) })

    def process(self, db, user, repository, branch, summary, commit_ids=None,
                commit_sha1s=None, applyfilters=True, applyparentfilters=True,
                reviewfilters=None, recipientfilters=None, description=None,
                frombranch=None, trackedbranch=None):
        # Raises auth.AccessDenied if access should not be allowed.
        repository.checkAccess(db, "modify")

        if not branch.startswith("r/"):
            raise OperationFailure(code="invalidbranch",
                                   title="Invalid review branch name",
                                   message="'%s' is not a valid review branch name; it must have a \"r/\" prefix." % branch)

        if reviewfilters is None:
            reviewfilters = []
        if recipientfilters is None:
            recipientfilters = {}

        components = branch.split("/")
        for index in range(1, len(components)):
            try:
                repository.revparse("refs/heads/%s" % "/".join(components[:index]))
            except gitutils.GitReferenceError:
                continue

            message = ("Cannot create branch with name<pre>%s</pre>since there is already a branch named<pre>%s</pre>in the repository." %
                       (htmlutils.htmlify(branch), htmlutils.htmlify("/".join(components[:index]))))
            raise OperationFailure(code="invalidbranch",
                                   title="Invalid review branch name",
                                   message=message,
                                   is_html=True)

        if commit_sha1s is not None:
            commits = [gitutils.Commit.fromSHA1(db, repository, commit_sha1) for commit_sha1 in commit_sha1s]
        elif commit_ids is not None:
            commits = [gitutils.Commit.fromId(db, repository, commit_id) for commit_id in commit_ids]
        else:
            commits = []

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
            if extensions.role.processcommits.execute(db, user, review, commits, None, commitset.getHeads().pop(), extensions_output):
                kwargs["extensions_output"] = extensions_output.getvalue().lstrip()

        if trackedbranch:
            cursor = db.cursor()

            cursor.execute("""SELECT 1
                                FROM knownremotes
                               WHERE url=%s
                                 AND pushing""",
                           (trackedbranch["remote"],))

            if cursor.fetchone():
                delay = "1 week"
            else:
                delay = "1 hour"

            cursor.execute("""INSERT INTO trackedbranches (repository, local_name, remote, remote_name, forced, delay)
                                   VALUES (%s, %s, %s, %s, false, INTERVAL %s)
                                RETURNING id""",
                           (repository.id, branch, trackedbranch["remote"], trackedbranch["name"], delay))

            trackedbranch_id = cursor.fetchone()[0]
            kwargs["trackedbranch_id"] = trackedbranch_id

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
        except gitutils.GitCommandError as error:
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
        Operation.__init__(self, { "repository": Repository,
                                   "remote": str,
                                   "branch": str,
                                   "upstream": Optional(str) },
                           accept_anonymous_user=True)

    def process(self, db, user, repository, remote, branch, upstream="refs/heads/master"):
        # Raises auth.AccessDenied if access should not be allowed.
        repository.checkAccess(db, "modify")

        cursor = db.cursor()

        # Check if only other repositories are currently tracking branches from
        # this remote.  If that's the case, then the user most likely either
        # selected the wrong repository or entered the wrong remote.
        cursor.execute("""SELECT repositories.name
                            FROM repositories
                            JOIN trackedbranches ON (trackedbranches.repository=repositories.id)
                           WHERE trackedbranches.remote=%s""",
                       (remote,))
        repository_names = set(repository_name for repository_name, in cursor)
        if repository_names and repository.name not in repository_names:
            raise OperationFailure(
                code="badremote",
                title="Bad remote!",
                message=("The remote <code>%s</code> appears to be related to "
                         "%s on this server (<code>%s</code>).  "
                         "You most likely shouldn't be importing branches from "
                         "it into the selected repository (<code>%s</code>)."
                         % (htmlutils.htmlify(remote),
                            ("another repository"
                             if len(repository_names) == 1 else
                             "other repositories"),
                            htmlutils.htmlify(", ".join(sorted(repository_names))),
                            htmlutils.htmlify(repository.name))),
                is_html=True)

        if not branch.startswith("refs/"):
            branch = "refs/heads/%s" % branch

        try:
            with repository.fetchTemporaryFromRemote(db, remote, branch) as sha1:
                head_sha1 = repository.keepalive(sha1)
        except gitutils.GitReferenceError as error:
            if error.repository:
                raise OperationFailure(
                    code="refnotfound",
                    title="Remote ref not found!",
                    message=("Could not find the ref <code>%s</code> in the repository <code>%s</code>."
                             % (htmlutils.htmlify(error.ref), htmlutils.htmlify(error.repository))),
                    is_html=True)
            else:
                raise OperationFailure(
                    code="invalidref",
                    title="Invalid ref!",
                    message=("The specified ref is invalid: <code>%s</code>."
                             % htmlutils.htmlify(error.ref)),
                    is_html=True)
        except gitutils.GitCommandError as error:
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
            try:
                with repository.fetchTemporaryFromRemote(db, remote, upstream) as sha1:
                    upstream_sha1 = repository.keepalive(sha1)
            except gitutils.GitReferenceError:
                raise OperationFailure(
                    code="refnotfound",
                    title="Remote ref not found!",
                    message=("Could not find the ref <code>%s</code> in the repository <code>%s</code>."
                             % (htmlutils.htmlify(upstream), htmlutils.htmlify(remote))),
                    is_html=True)
        else:
            try:
                upstream_sha1 = repository.revparse(upstream)
            except gitutils.GitReferenceError:
                raise OperationFailure(
                    code="refnotfound",
                    title="Local ref not found!",
                    message=("Could not find the ref <code>%s</code> in the repository <code>%s</code>."
                             % (htmlutils.htmlify(upstream), htmlutils.htmlify(str(repository)))),
                    is_html=True)

        try:
            resolved_upstream_sha1 = gitutils.getTaggedCommit(repository, upstream_sha1)
        except gitutils.GitReferenceError:
            resolved_upstream_sha1 = None

        if not resolved_upstream_sha1:
            raise OperationFailure(
                code="missingcommit",
                title="Upstream commit is missing!",
                message=("<p>Could not find the commit <code>%s</code> in the "
                         "repository <code>%s</code>.</p>"
                         "<p>Since it would have been fetched along with the "
                         "branch if it actually was a valid upstream commit, "
                         "this means it's not valid.</p>"
                         % (htmlutils.htmlify(upstream_sha1), htmlutils.htmlify(str(repository)))),
                is_html=True)

        commit_sha1s = repository.revlist(included=[head_sha1], excluded=[resolved_upstream_sha1])

        if not commit_sha1s:
            raise OperationFailure(
                code="emptybranch",
                title="Branch contains no commits!",
                message=("All commits referenced by <code>%s</code> are reachable from <code>%s</code>."
                         % (htmlutils.htmlify(branch), htmlutils.htmlify(upstream))),
                is_html=True)

        cursor.execute("SELECT id FROM commits WHERE sha1=ANY (%s)", (commit_sha1s,))

        return OperationResult(commit_ids=[commit_id for (commit_id,) in cursor],
                               head_sha1=head_sha1, upstream_sha1=resolved_upstream_sha1)
