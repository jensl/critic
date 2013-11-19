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

from subprocess import Popen as process, PIPE
from re import compile, split
from time import gmtime, strftime
from pwd import getpwuid
from os import getuid

from dbutils import *
import gitutils
from log.commitset import CommitSet

import dbutils
import reviewing.utils
import reviewing.mail
import reviewing.rebase
import configuration
import log.commitset
import textutils

if configuration.extensions.ENABLED:
    import extensions.role.processcommits

try:
    from customization.email import getUserEmailAddress
except ImportError:
    def getUserEmailAddress(_username):
        return None

try:
    from customization.githook import Reject, update
except ImportError:
    class Reject(Exception):
        pass
    def update(_repository, _ref, _old, _new):
        pass

def timestamp(time):
    return strftime("%Y-%m-%d %H:%M:%S", time)

def getUser(db, user_name):
    if user_name == configuration.base.SYSTEM_USER_NAME:
        return user_name
    try:
        return dbutils.User.fromName(db, user_name)
    except dbutils.NoSuchUser:
        if configuration.base.AUTHENTICATION_MODE == "host":
            email = getUserEmailAddress(user_name)
            user = dbutils.User.create(
                db, user_name, user_name, email, email_verified=None)
            db.commit()
            return user
        raise

db = None

class IndexException(Exception):
    pass

def processCommits(repository_name, sha1):
    repository = gitutils.Repository.fromName(db, repository_name)

    if not repository: raise IndexException("No such repository: %r" % repository_name)

    stack = []
    edges_values = []

    cursor = db.cursor()
    cursor.execute("SELECT 1 FROM commits LIMIT 1")
    emptydb = cursor.fetchone() is None

    cursor.execute("""SELECT commits.sha1
                        FROM commits
                        JOIN branches ON (branches.head=commits.id)
                       WHERE branches.repository=%s
                         AND branches.type='normal'
                         AND branches.base IS NULL
                    ORDER BY branches.id ASC""",
                   (repository.id,))

    try:
        base_sha1 = cursor.fetchone()[0]
        count = int(repository.run("rev-list", "--count", "%s..%s" % (base_sha1, sha1)).strip())
    except:
        count = 0

    if count > configuration.limits.PUSH_COMMIT_LIMIT:
        raise IndexException("""\
You're trying to add %d new commits to this repository.  Are you
perhaps pushing to the wrong repository?""" % count)

    commits_values = []
    commits = set()

    while True:
        if sha1 not in commits:
            commit = gitutils.Commit.fromSHA1(db, repository, sha1)

            if commit.author.email: author_id = commit.author.getGitUserId(db)
            else: author_id = 0

            if commit.committer.email: committer_id = commit.committer.getGitUserId(db)
            else: committer_id = 0

            if emptydb: row = None
            else:
                cursor.execute("SELECT id FROM commits WHERE sha1=%s", (commit.sha1,))
                row = cursor.fetchone()
                new_commit = False

            if not row:
                commits_values.append((commit.sha1, author_id, committer_id, timestamp(commit.author.time), timestamp(commit.committer.time)))
                new_commit = True

            commits.add(sha1)

            if new_commit:
                edges_values.extend([(parent_sha1, commit.sha1) for parent_sha1 in set(commit.parents)])
                stack.extend(set(commit.parents))

        if not stack: break

        sha1 = stack.pop(0)

    cursor.executemany("""INSERT INTO commits (sha1, author_gituser, commit_gituser, author_time, commit_time)
                               VALUES (%s, %s, %s, %s, %s)""",
                       commits_values)

    cursor.executemany("""INSERT INTO edges (parent, child)
                               SELECT parents.id, children.id
                                 FROM commits AS parents,
                                      commits AS children
                                WHERE parents.sha1=%s AND children.sha1=%s""",
                       edges_values)

    db.commit()

def init():
    global db

    db = Database()

def finish():
    global db

    if db:
        db.commit()
        db.close()
        db = None

def abort():
    global db

    if db:
        db.rollback()
        db.close()
        db = None

def createBranches(user_name, repository_name, branches, flags):
    user = getUser(db, user_name)
    repository = gitutils.Repository.fromName(db, repository_name)

    for name, head in branches: processCommits(repository_name, head)

    if len(branches) > 1:
        try:
            from customization.branches import compareBranchNames
        except ImportError:
            def compareBranchNames(name1, name2):
                name1 = split("([-_+])", name1)
                name2 = split("([-_+])", name2)

                for name1, name2 in map(None, name1, name2):
                    if name1 is None: return -1
                    elif name2 is None: return 1
                    elif name1 != name2:
                        try: return cmp(int(name1), int(name2))
                        except: return cmp(name1, name2)
                else: return 0

        def compareBranches(branch1, branch2):
            name1, head1 = branch1
            name2, head2 = branch2

            # Same name ought not occur twice, but just to be on the safe side.
            if name1 == name2: return 0

            # Special case for master.  Mostly redundant, because it's quite
            # unlikely that master would be created along with other branches.
            elif name1 == "master": return -1
            elif name2 == "master": return 1

            # Try a natural ordering based on the relationships of the head
            # commits of the two branches, unless the heads are the same:
            if head1 != head2:
                base = repository.mergebase([head1, head2])

                # If either head is an ancestor of the other head, merge-base
                # between them will be the ancestor head, and in that case,
                # process that branch first.  Otherwise, then that would be
                # guaranteed to show up as empty, and that's probably not the
                # intention.
                if base == head1: return -1
                elif base == head2: return 1

            # Two non-taskbranch branches that seem "unrelated".  Process them
            # ordered by name, mostly so that this comparison function is well-
            # behaved.
            return compareBranchNames(name1, name2)

        branches.sort(cmp=compareBranches)

    for name, head in branches: createBranch(user, repository, name, head, flags)

def createBranch(user, repository, name, head, flags):
    processCommits(repository.name, head)

    try:
        update(repository.path, "refs/heads/" + name, None, head)
    except Reject as rejected:
        raise IndexException(str(rejected))
    except Exception:
        pass

    cursor = db.cursor()

    def commit_id(sha1):
        cursor.execute("SELECT id FROM commits WHERE sha1=%s", [sha1])
        return cursor.fetchone()[0]

    components = name.split("/")
    for index in range(1, len(components)):
        try: repository.revparse("refs/heads/%s" % "/".join(components[:index]))
        except: continue

        message = ("Cannot create branch with name '%s' since there is already a branch named '%s' in the repository." %
                   (name, "/".join(components[:index])))
        raise IndexException(textutils.reflow(message, line_length=80 - len("remote: ")))

    if name.startswith("r/"):
        try:
            review_id = int(name[2:])

            cursor.execute("SELECT branches.name FROM reviews JOIN branches ON (branches.id=reviews.branch) WHERE reviews.id=%s", (review_id,))
            row = cursor.fetchone()

            message = "Refusing to create review named as a number."

            if row:
                message += "\nDid you mean to push to the branch '%s', perhaps?" % row[0]

            raise IndexException(message)
        except ValueError:
            pass

        if user.getPreference(db, "review.createViaPush"):
            the_commit = gitutils.Commit.fromSHA1(db, repository, head, commit_id(head))
            all_commits = [the_commit]

            review = reviewing.utils.createReview(
                db, user, repository, all_commits, name,
                the_commit.niceSummary(include_tag=False), None, via_push=True)

            print "Submitted review:"
            print review.getURL(db, user, indent=2)

            if review.reviewers:
                print "  Reviewers:"
                for reviewer in review.reviewers:
                    print "    %s <%s>" % (reviewer.fullname, reviewer.email)

            if review.watchers:
                print "  Watchers:"
                for watcher in review.watchers:
                    print "    %s <%s>" % (watcher.fullname, watcher.email)

            if configuration.extensions.ENABLED:
                if extensions.role.processcommits.execute(db, user, review, all_commits, None, the_commit, sys.stdout):
                    print

            print "Thank you!"
            return True
        else:
            raise IndexException("Refusing to create review; user preference 'review.createViaPush' is not enabled.")

    sha1 = head
    base = None
    tail = None

    cursor.execute("""SELECT 1
                        FROM reachable
                        JOIN branches ON (branches.id=reachable.branch)
                        JOIN repositories ON (repositories.id=branches.repository)
                       WHERE repositories.id=%s
                       LIMIT 1""",
                   (repository.id,))

    if cursor.fetchone():
        def reachable(sha1):
            cursor.execute("""SELECT branches.id
                                FROM branches
                                JOIN reachable ON (reachable.branch=branches.id)
                                JOIN commits ON (commits.id=reachable.commit)
                               WHERE branches.repository=%s
                                 AND branches.type='normal'
                                 AND commits.sha1=%s
                            ORDER BY reachable.branch ASC
                               LIMIT 1""",
                           (repository.id, sha1))
            return cursor.fetchone()
    else:
        def reachable(sha1):
            return None

    commit_map = {}
    commit_list = []

    row = reachable(sha1)
    if row:
        # Head of branch is reachable from an existing branch.  Could be because
        # this branch is actually empty (just created with no "own" commits) or
        # it could have been merged into some other already existing branch.  We
        # can't tell, so we just record it as empty.

        base = row[0]
        tail = sha1
    else:
        stack = []

        while True:
            if sha1 not in commit_map:
                commit = gitutils.Commit.fromSHA1(db, repository, sha1)
                commit_map[sha1] = commit
                commit_list.append(commit)

                for sha1 in commit.parents:
                    if sha1 not in commit_map:
                        row = reachable(sha1)
                        if not row:
                            stack.append(sha1)
                        elif base is None:
                            base = row[0]
                            tail = sha1

                            base_chain = [base]

                            while True:
                                cursor.execute("SELECT base FROM branches WHERE id=%s", (base_chain[-1],))
                                next = cursor.fetchone()[0]
                                if next is None: break
                                else: base_chain.append(next)

                            def reachable(sha1):
                                cursor.execute("""SELECT 1
                                                    FROM reachable
                                                    JOIN commits ON (commits.id=reachable.commit)
                                                   WHERE reachable.branch=ANY (%s)
                                                     AND commits.sha1=%s""",
                                               (base_chain, sha1))
                                return cursor.fetchone()

            if stack: sha1 = stack.pop(0)
            else: break

    if isinstance(user, dbutils.User):
        # Push by regular user.
        user_name = user.name
    else:
        # Push by the Critic system user, i.e. by the branch tracker service or
        # other internal mechanism.
        user_name = user

    if not base:
        cursor.execute("INSERT INTO branches (repository, name, head) VALUES (%s, %s, %s) RETURNING id", (repository.id, name, commit_id(head)))
        branch_id = cursor.fetchone()[0]
    else:
        cursor.execute("INSERT INTO branches (repository, name, head, base, tail) VALUES (%s, %s, %s, %s, %s) RETURNING id", (repository.id, name, commit_id(head), base, commit_id(tail)))
        branch_id = cursor.fetchone()[0]

        # Suppress the "user friendly" feedback if the push is performed by the
        # Critic system user, since there wouldn't be a human being reading it.
        #
        # Also, the calls to user.getCriticURLs() obvious don't work if 'user'
        # isn't a dbutils.User object, which it isn't in that case.
        if user_name != configuration.base.SYSTEM_USER_NAME:
            cursor.execute("SELECT name FROM branches WHERE id=%s", [base])

            print "Added branch based on %s containing %d commit%s:" % (cursor.fetchone()[0], len(commit_list), "s" if len(commit_list) > 1 else "")
            for url_prefix in user.getCriticURLs(db):
                print "  %s/log?repository=%d&branch=%s" % (url_prefix, repository.id, name)
            if len(commit_list) > 1:
                print "To create a review of all %d commits:" % len(commit_list)
            else:
                print "To create a review of the commit:"
            for url_prefix in user.getCriticURLs(db):
                print "  %s/createreview?repository=%d&branch=%s" % (url_prefix, repository.id, name)

    reachable_values = [(branch_id, commit.sha1) for commit in commit_list]
    cursor.executemany("INSERT INTO reachable (branch, commit) SELECT %s, id FROM commits WHERE sha1=%s", reachable_values)

    if not repository.hasMainBranch() and user_name == configuration.base.SYSTEM_USER_NAME:
        cursor.execute("UPDATE repositories SET branch=%s WHERE id=%s", (branch_id, repository.id))

def updateBranch(user_name, repository_name, name, old, new, multiple, flags):
    repository = gitutils.Repository.fromName(db, repository_name)

    processCommits(repository_name, new)

    try:
        update(repository.path, "refs/heads/" + name, old, new)
    except Reject as rejected:
        raise IndexException(str(rejected))
    except Exception:
        pass

    try:
        branch = dbutils.Branch.fromName(db, repository, name)
        base_branch_id = branch.base.id if branch.base else None
    except:
        raise IndexException("The branch '%s' is not in the database!  (This should never happen.)" % name)

    if branch.head.sha1 != old:
        if new == branch.head.sha1:
            # This is what we think the ref ought to be already.  Do nothing,
            # and let the repository "catch up."
            return
        else:
            data = { "name": name,
                     "old": old[:8],
                     "new": new[:8],
                     "current": branch.head.sha1[:8] }

            message = """CONFUSED!  Git thinks %(name)s points to %(old)s, but Critic thinks it points to %(current)s.  Rejecting push since it would only makes matters worse.  To resolve this problem, use

  git push -f critic %(current)s:%(name)s

to resynchronize the Git repository with Critic's database.  Note that 'critic' above must be replaced by the actual name of your Critic remote, if not 'critic'.""" % data

            raise IndexException(textutils.reflow(message, line_length=80 - len("remote: ")))

    cursor = db.cursor()
    cursor.execute("""SELECT id, remote, remote_name, forced, updating
                        FROM trackedbranches
                       WHERE repository=%s
                         AND local_name=%s
                         AND NOT disabled""",
                   (repository.id, name))
    row = cursor.fetchone()

    if row:
        trackedbranch_id, remote, remote_name, forced, updating = row
        tracked_branch = "%s in %s" % (remote_name, remote)

        assert not forced or not name.startswith("r/")

        if user_name != configuration.base.SYSTEM_USER_NAME \
                or flags.get("trackedbranch_id") != str(trackedbranch_id):
            raise IndexException("""\
The branch '%s' is set up to track '%s' in
  %s
Please don't push it manually to this repository.""" % (name, remote_name, remote))

        assert updating

        if not name.startswith("r/"):
            conflicting = repository.revlist([branch.head.sha1], [new])
            added = repository.revlist([new], [branch.head.sha1])

            if conflicting:
                if forced:
                    if branch.base is None:
                        cursor.executemany("""DELETE FROM reachable
                                                    USING commits
                                                    WHERE reachable.branch=%s
                                                      AND reachable.commit=commits.id
                                                      AND commits.sha1=%s""",
                                           [(branch.id, sha1) for sha1 in conflicting])
                    else:
                        print "Non-fast-forward update detected; deleting and recreating branch."

                        deleteBranch(user_name, repository.name, branch.name, old)
                        createBranches(user_name, repository.name, [(branch.name, new)], flags)

                        return
                else:
                    raise IndexException("""\
Rejecting non-fast-forward update of branch.  To perform the update, you
can delete the branch using
  git push critic :%s
first, and then repeat this push.""" % name)

            cursor.executemany("""INSERT INTO reachable (branch, commit)
                                       SELECT %s, commits.id
                                         FROM commits
                                        WHERE sha1=%s""",
                               [(branch.id, sha1) for sha1 in added])

            new_head = gitutils.Commit.fromSHA1(db, repository, new)

            cursor.execute("UPDATE branches SET head=%s WHERE id=%s",
                           (new_head.getId(db), branch.id))

            output = []

            if conflicting:
                output.append("Pruned %d conflicting commits." % len(conflicting))
            if added:
                output.append("Added %d new commits." % len(added))

            if output:
                print "\n".join(output)

            return
    else:
        tracked_branch = False

    user = getUser(db, user_name)

    if isinstance(user, str):
        user = dbutils.User(
            0, configuration.base.SYSTEM_USER_NAME, "Critic System", "current",
            configuration.base.SYSTEM_USER_EMAIL, None)

    cursor.execute("SELECT id FROM reviews WHERE branch=%s", (branch.id,))
    row = cursor.fetchone()

    is_review = bool(row)

    if is_review:
        if multiple:
            raise IndexException("""\
Refusing to update review in push of multiple refs.  Please push one
review branch at a time.""")

        review_id = row[0]

        cursor.execute("""SELECT id, old_head, old_upstream, new_upstream, uid, branch
                            FROM reviewrebases
                           WHERE review=%s AND new_head IS NULL""",
                       (review_id,))
        row = cursor.fetchone()

        if row:
            if tracked_branch:
                raise IndexException("Refusing to perform a review rebase via an automatic update.")

            rebase_id, old_head_id, old_upstream_id, new_upstream_id, rebaser_id, onto_branch = row

            review = dbutils.Review.fromId(db, review_id)
            rebaser = dbutils.User.fromId(db, rebaser_id)

            if rebaser.id != user.id:
                if user_name == configuration.base.SYSTEM_USER_NAME:
                    user = rebaser
                else:
                    raise IndexException("""\
This review is currently being rebased by
  %s <%s>
and can't be otherwise updated right now.""" % (rebaser.fullname, rebaser.email))

            old_head = gitutils.Commit.fromId(db, repository, old_head_id)
            old_commitset = log.commitset.CommitSet(review.branch.commits)

            if old_head.sha1 != old:
                raise IndexException("""\
Unexpected error.  The branch appears to have been updated since your
rebase was prepared.  You need to cancel the rebase via the review
front-page and then try again, and/or report a bug about this error.""")

            if old_upstream_id is not None:
                new_head = gitutils.Commit.fromSHA1(db, repository, new)

                old_upstream = gitutils.Commit.fromId(db, repository, old_upstream_id)

                if new_upstream_id is not None:
                    new_upstream = gitutils.Commit.fromId(db, repository, new_upstream_id)
                else:
                    if len(new_head.parents) != 1:
                        raise IndexException("Invalid rebase: New head can't be a merge commit.")

                    new_upstream = gitutils.Commit.fromSHA1(db, repository, new_head.parents[0])

                    if new_upstream in old_commitset.getTails():
                        old_upstream = new_upstream = None
            else:
                old_upstream = None

            if old_upstream:
                unrelated_move = False

                if not new_upstream.isAncestorOf(new):
                    raise IndexException("""\
Invalid rebase: The new upstream commit you specified when the rebase
was prepared is not an ancestor of the commit now pushed.  You may want
to cancel the rebase via the review front-page, and prepare another one
specifying the correct new upstream commit; or rebase the branch onto
the new upstream specified and then push that instead.""")

                if not old_upstream.isAncestorOf(new_upstream):
                    unrelated_move = True

                if unrelated_move:
                    replayed_rebase = reviewing.rebase.replayRebase(
                        db, review, user, old_head, old_upstream, new_head,
                        new_upstream, onto_branch)
                else:
                    merge = reviewing.rebase.createEquivalentMergeCommit(
                        db, review, user, old_head, old_upstream, new_head,
                        new_upstream, onto_branch)

                new_sha1s = repository.revlist([new_head.sha1], [new_upstream.sha1], '--topo-order')
                rebased_commits = [gitutils.Commit.fromSHA1(db, repository, sha1) for sha1 in new_sha1s]
                reachable_values = [(review.branch.id, sha1) for sha1 in new_sha1s]

                pending_mails = []

                recipients = review.getRecipients(db)
                for to_user in recipients:
                    pending_mails.extend(reviewing.mail.sendReviewRebased(
                            db, user, to_user, recipients, review,
                            new_upstream, rebased_commits, onto_branch))

                print "Rebase performed."

                review.setPerformedRebase(old_head, new_head, old_upstream, new_upstream, user)

                if unrelated_move:
                    reviewing.utils.addCommitsToReview(
                        db, user, review, [replayed_rebase],
                        pending_mails=pending_mails,
                        silent_if_empty=set([replayed_rebase]),
                        replayed_rebases={ replayed_rebase: new_head })

                    repository.keepalive(old_head)
                    repository.keepalive(replayed_rebase)
                else:
                    reviewing.utils.addCommitsToReview(
                        db, user, review, [merge], pending_mails=pending_mails,
                        silent_if_empty=set([merge]), full_merges=set([merge]))

                    repository.keepalive(merge)

                if not unrelated_move:
                    cursor.execute("""UPDATE reviewrebases
                                         SET old_head=%s
                                       WHERE review=%s AND new_head IS NULL""",
                                   (merge.id, review.id))

                cursor.execute("""UPDATE reviewrebases
                                     SET new_head=%s, new_upstream=%s
                                   WHERE review=%s AND new_head IS NULL""",
                               (new_head.getId(db), new_upstream.getId(db), review.id))

                cursor.execute("""INSERT INTO previousreachable (rebase, commit)
                                       SELECT %s, commit
                                         FROM reachable
                                        WHERE branch=%s""",
                               (rebase_id, review.branch.id))
                cursor.execute("DELETE FROM reachable WHERE branch=%s",
                               (review.branch.id,))
                cursor.executemany("""INSERT INTO reachable (branch, commit)
                                           SELECT %s, commits.id
                                             FROM commits
                                            WHERE commits.sha1=%s""",
                                   reachable_values)
                cursor.execute("UPDATE branches SET head=%s WHERE id=%s",
                               (new_head.getId(db), review.branch.id))
            else:
                old_commitset = log.commitset.CommitSet(review.branch.commits)
                new_sha1s = repository.revlist([new], old_commitset.getTails(), '--topo-order')

                if old_head.sha1 in new_sha1s:
                    raise IndexException("""\
Invalid history rewrite: Old head of the branch reachable from the
pushed ref; no history rewrite performed.  (Cancel the rebase via
the review front-page if you've changed your mind.)""")

                for new_sha1 in new_sha1s:
                    new_head = gitutils.Commit.fromSHA1(db, repository, new_sha1)
                    if new_head.tree == old_head.tree: break
                else:
                    raise IndexException("""\
Invalid history rewrite: No commit on the rebased branch references
the same tree as the old head of the branch.""")

                rebased_commits = [gitutils.Commit.fromSHA1(db, repository, sha1) for sha1 in repository.revlist([new_head], old_commitset.getTails(), '--topo-order')]
                new_commits = [gitutils.Commit.fromSHA1(db, repository, sha1) for sha1 in repository.revlist([new], [new_head], '--topo-order')]
                reachable_values = [(review.branch.id, sha1) for sha1 in new_sha1s]

                pending_mails = []

                recipients = review.getRecipients(db)
                for to_user in recipients:
                    pending_mails.extend(reviewing.mail.sendReviewRebased(db, user, to_user, recipients, review, None, rebased_commits))

                print "History rewrite performed."

                if new_commits:
                    reviewing.utils.addCommitsToReview(db, user, review, new_commits, pending_mails=pending_mails)
                else:
                    reviewing.mail.sendPendingMails(pending_mails)

                cursor.execute("""UPDATE reviewrebases
                                     SET new_head=%s
                                   WHERE review=%s AND new_head IS NULL""",
                               (new_head.getId(db), review.id))

                cursor.execute("""INSERT INTO previousreachable (rebase, commit)
                                       SELECT %s, commit
                                         FROM reachable
                                        WHERE branch=%s""",
                               (rebase_id, review.branch.id))
                cursor.execute("DELETE FROM reachable WHERE branch=%s",
                               (review.branch.id,))
                cursor.executemany("""INSERT INTO reachable (branch, commit)
                                           SELECT %s, commits.id
                                             FROM commits
                                            WHERE commits.sha1=%s""",
                                   reachable_values)
                cursor.execute("UPDATE branches SET head=%s WHERE id=%s",
                               (gitutils.Commit.fromSHA1(db, repository, new).getId(db),
                                review.branch.id))

                repository.run('update-ref', 'refs/keepalive/%s' % old, old)

            review.incrementSerial(db)

            return True
        elif old != repository.mergebase([old, new]):
            raise IndexException("Rejecting non-fast-forward update of review branch.")
    elif old != repository.mergebase([old, new]):
        raise IndexException("""\
Rejecting non-fast-forward update of branch.  To perform the update, you
can delete the branch using
  git push critic :%s
first, and then repeat this push.""" % name)

    cursor.execute("SELECT id FROM branches WHERE repository=%s AND base IS NULL ORDER BY id ASC LIMIT 1", (repository.id,))
    root_branch_id = cursor.fetchone()[0]

    def isreachable(sha1):
        if is_review and sha1 == branch.tail: return True
        if base_branch_id: cursor.execute("SELECT 1 FROM commits, reachable WHERE commits.sha1=%s AND commits.id=reachable.commit AND reachable.branch IN (%s, %s, %s)", [sha1, branch.id, base_branch_id, root_branch_id])
        else: cursor.execute("SELECT 1 FROM commits, reachable WHERE commits.sha1=%s AND commits.id=reachable.commit AND reachable.branch IN (%s, %s)", [sha1, branch.id, root_branch_id])
        return cursor.fetchone() is not None

    stack = [new]
    commits = set()
    commit_list = []
    processed = set()

    while stack:
        sha1 = stack.pop()

        if sha1 not in commits and not isreachable(sha1):
            commits.add(sha1)
            commit_list.append(sha1)

            stack.extend([parent_sha1 for parent_sha1 in gitutils.Commit.fromSHA1(db, repository, sha1).parents if parent_sha1 not in processed])

        processed.add(sha1)

    branch = dbutils.Branch.fromName(db, repository, name)
    review = dbutils.Review.fromBranch(db, branch)

    if review:
        if review.state != "open":
            raise IndexException("""\
The review is closed and can't be extended.  You need to reopen it at
%s
before you can add commits to it.""" % review.getURL(db, user, 2))

        all_commits = [gitutils.Commit.fromSHA1(db, repository, sha1) for sha1 in reversed(commit_list)]

        tails = CommitSet(all_commits).getTails()

        if old not in tails:
            raise IndexException("""\
Push rejected; would break the review.

It looks like some of the pushed commits are reachable from the
repository's main branch, and thus consequently the commits currently
included in the review are too.

Perhaps you should request a new review of the follow-up commits?""")

        reviewing.utils.addCommitsToReview(db, user, review, all_commits, commitset=commits, tracked_branch=tracked_branch)

    reachable_values = [(branch.id, sha1) for sha1 in reversed(commit_list) if sha1 in commits]

    cursor.executemany("INSERT INTO reachable (branch, commit) SELECT %s, commits.id FROM commits WHERE commits.sha1=%s", reachable_values)
    cursor.execute("UPDATE branches SET head=%s WHERE id=%s", (gitutils.Commit.fromSHA1(db, repository, new).getId(db), branch.id))

    db.commit()

    if configuration.extensions.ENABLED and review:
        extensions.role.processcommits.execute(db, user, review, all_commits,
                                               gitutils.Commit.fromSHA1(db, repository, old),
                                               gitutils.Commit.fromSHA1(db, repository, new),
                                               sys.stdout)

def deleteBranch(user_name, repository_name, name, old):
    repository = gitutils.Repository.fromName(db, repository_name)

    try:
        update(repository.path, "refs/heads/" + name, old, None)
    except Reject as rejected:
        raise IndexException(str(rejected))
    except Exception:
        pass

    branch = dbutils.Branch.fromName(db, repository, name)

    if branch:
        review = dbutils.Review.fromBranch(db, branch)

        if review:
            raise IndexException("This is Critic refusing to delete a branch that belongs to a review.")

        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM reachable WHERE branch=%s", (branch.id,))

        ncommits = cursor.fetchone()[0]

        if branch.base:
            cursor.execute("UPDATE branches SET base=%s WHERE base=%s", (branch.base.id, branch.id))

        cursor.execute("DELETE FROM branches WHERE id=%s", (branch.id,))

        # Suppress the "user friendly" feedback if the push is performed by the
        # Critic system user, since there wouldn't be a human being reading it.
        if user_name != configuration.base.SYSTEM_USER_NAME:
            print "Deleted branch containing %d commit%s." % (ncommits, "s" if ncommits > 1 else "")

def createTag(repository_name, name, sha1):
    repository = gitutils.Repository.fromName(db, repository_name)

    sha1 = gitutils.getTaggedCommit(repository, sha1)

    if sha1:
        processCommits(repository.name, sha1)

        cursor = db.cursor()
        cursor.execute("INSERT INTO tags (name, repository, sha1) VALUES (%s, %s, %s)",
                       (name, repository.id, sha1))

def updateTag(repository_name, name, old_sha1, new_sha1):
    repository = gitutils.Repository.fromName(db, repository_name)

    sha1 = gitutils.getTaggedCommit(repository, new_sha1)
    cursor = db.cursor()

    if sha1:
        processCommits(repository.name, sha1)

        cursor.execute("UPDATE tags SET sha1=%s WHERE name=%s AND repository=%s",
                       (sha1, name, repository.id))
    else:
        cursor.execute("DELETE FROM tags WHERE name=%s AND repository=%s",
                       (name, repository.id))

def deleteTag(repository_name, name):
    repository = gitutils.Repository.fromName(db, repository_name)

    cursor = db.cursor()
    cursor.execute("DELETE FROM tags WHERE name=%s AND repository=%s",
                   (name, repository.id))
