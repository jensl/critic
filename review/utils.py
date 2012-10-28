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

import dbutils
from dbutils import *
from itertools import izip, repeat, chain
import htmlutils

import mail
import changeset.utils as changeset_utils
import review.comment as review_comment
import log.commitset as log_commitset

from operation import OperationError, OperationFailure
from filters import Filters

def checkCommitChain(commits):
    """checkCommitChain(commits)

Verifies that the list of commits is suitable for a review, meaning that
no commits is a merge and that each commit is the parent of the following
commit.  If not, throws an exception describing the issue."""

    if len(commits) > 1:
        for commit in commits:
            if len(commit.parents) > 1:
                raise Exception, "%s is a merge commit" % commit.sha1
            elif len(commit.parents) == 0:
                raise Exception, "%s is a root commit" % commit.sha1

        for parent, child in zip(commits, commits[1:]):
            if parent.sha1 not in child.parents:
                raise Exception, "%s is not a parent of %s" % (parent.sha1, child.sha1)

def getReviewersAndWatchers(db, repository, commits=None, changesets=None, reviewfilters=None, applyfilters=True, applyparentfilters=False, parentfiltersonly=False):
    """getReviewersAndWatchers(db, commits=None, changesets=None) -> tuple

Returns a tuple containing two dictionaries, each mapping file IDs to
dictionaries mapping user IDs to sets of changeset IDs.  The first dictionary
defines the reviwers of each file, the second dictionary defines the watchers of
each file.  For any changes in a file for which no reviewer is identified, None
is used as a key in the dictionary instead of a real user ID."""

    if changesets is None:
        changesets = []
        changeset_utils.createChangesets(db, repository, commits)
        for commit in commits:
            changesets.extend(changeset_utils.createChangeset(db, None, repository, commit, do_highlight=False))

    cursor = db.cursor()

    filters = Filters()

    if applyfilters:
        if parentfiltersonly:
            filters.load(db, repository=repository.parent, recursive=True)
        else:
            filters.load(db, repository=repository, recursive=applyparentfilters)

    if reviewfilters:
        filters.addFilters(db, reviewfilters, sort=True)

    reviewers = {}
    watchers = {}

    for changeset in changesets:
        author_user_id = changeset.child.author.getUserId(db) if changeset.child else None

        cursor.execute("SELECT DISTINCT file FROM fileversions WHERE changeset=%s", (changeset.id,))

        for (file_id,) in cursor:
            reviewers_found = False

            for user_id, (filter_type, delegate) in filters.listUsers(db, file_id).items():
                try: assert isinstance(user_id, int)
                except: raise Exception, repr(filters.listUsers(db, file_id))

                if filter_type == 'reviewer':
                    if author_user_id != user_id:
                        reviewer_user_ids = [user_id]
                    elif delegate:
                        reviewer_user_ids = []
                        for delegate_user_name in delegate.split(","):
                            delegate_user = dbutils.User.fromName(db, delegate_user_name)
                            if delegate_user: reviewer_user_ids.append(delegate_user.id)
                            else: raise Exception, repr((user_id, delegate_user_name, file_id))
                    else:
                        reviewer_user_ids = []

                    for reviewer_user_id in reviewer_user_ids:
                        reviewers.setdefault(file_id, {}).setdefault(reviewer_user_id, set()).add(changeset.id)
                        reviewers_found = True
                else:
                    watchers.setdefault(file_id, {}).setdefault(user_id, set()).add(changeset.id)

            if not reviewers_found:
                reviewers.setdefault(file_id, {}).setdefault(None, set()).add(changeset.id)

    return reviewers, watchers

def getReviewedReviewers(db, review):
    """getReviewedReviewers(db, review) -> dictionary

Returns a dictionary, like the ones returned by getReviewersAndWatchers(), but
with details about all reviewed changes in the review."""

    cursor = db.cursor()

    cursor.execute("""SELECT reviewfiles.reviewer, reviewfiles.changeset, reviewfiles.file
                        FROM reviewfiles
                       WHERE reviewfiles.review=%s
                         AND reviewfiles.state='reviewed'""",
                   (review.id,))

    reviewers = {}

    for user_id, changeset_id, file_id in cursor.fetchall():
        reviewers.setdefault(file_id, {}).setdefault(user_id, set()).add(changeset_id)

    return reviewers

def getPendingReviewers(db, review):
    """getPendingReviewers(db, review) -> dictionary

Returns a dictionary, like the ones returned by getReviewersAndWatchers(), but
with details about remaining unreviewed changes in the review.  Changes not
assigned to a reviewer are handled the same way."""

    cursor = db.cursor()

    cursor.execute("""SELECT reviewuserfiles.uid, reviewfiles.changeset, reviewfiles.file
                        FROM reviewfiles
             LEFT OUTER JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                       WHERE reviewfiles.review=%s
                         AND reviewfiles.state='pending'""",
                   (review.id,))

    reviewers = {}

    for user_id, changeset_id, file_id in cursor.fetchall():
        reviewers.setdefault(file_id, {}).setdefault(user_id, set()).add(changeset_id)

    return reviewers

def collectReviewTeams(reviewers):
    """collectReviewTeams(reviewers) -> dictionary

Takes a dictionary as returned by getReviewersAndWatchers() or
getPendingReviewers() and transform into a dictionary mapping sets of users to
sets of files that those groups of users share review responsibilities for.  The
same user may appear in number of sets, as may the same file.

If None appears as a key in the returned dictionary, the set of files it is
mapped to have changes in them with no assigned reviewers."""

    teams = {}

    for file_id, file_reviewers in reviewers.items():
        if None in file_reviewers:
            teams.setdefault(None, set()).add(file_id)
        team = frozenset(filter(None, file_reviewers.keys()))
        if team: teams.setdefault(team, set()).add(file_id)

    return teams

def assignChanges(db, user, review, commits=None, changesets=None, update=False, parentfiltersonly=False):
    cursor = db.cursor()

    if changesets is None:
        assert commits is not None

        changesets = []

        for commit in commits:
            changesets.extend(changeset_utils.createChangeset(db, user, review.repository, commit))

    applyfilters = review.applyfilters
    applyparentfilters = review.applyparentfilters

    # Doesn't make sense to apply only parent filters if they're not supposed to
    # be applied in the first place.
    assert not parentfiltersonly or applyparentfilters

    reviewers, watchers = getReviewersAndWatchers(db, review.repository, changesets=changesets, reviewfilters=review.getReviewFilters(db), applyfilters=applyfilters, applyparentfilters=applyparentfilters, parentfiltersonly=parentfiltersonly)

    cursor.execute("SELECT uid FROM reviewusers WHERE review=%s", (review.id,))

    reviewusers = set([user_id for (user_id,) in cursor])
    reviewusers_values = set()
    reviewuserfiles_values = set()

    reviewuserfiles_existing = {}

    if update:
        cursor.execute("""SELECT reviewuserfiles.uid, reviewfiles.changeset, reviewfiles.file
                            FROM reviewfiles
                            JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                           WHERE reviewfiles.review=%s""", (review.id,))
        for user_id, changeset_id, file_id in cursor:
            reviewuserfiles_existing[(user_id, changeset_id, file_id)] = True

    new_reviewers = set()
    new_watchers = set()

    cursor.execute("""SELECT DISTINCT uid
                        FROM reviewfiles
                        JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                       WHERE review=%s""", (review.id,))
    old_reviewers = set([user_id for (user_id,) in cursor])

    for file_id, file_users in reviewers.items():
        for user_id, user_changesets in file_users.items():
            if user_id:
                new_reviewers.add(user_id)

                if user_id not in reviewusers:
                    reviewusers.add(user_id)
                    reviewusers_values.add((review.id, user_id))
                for changeset_id in user_changesets:
                    if (user_id, changeset_id, file_id) not in reviewuserfiles_existing:
                        reviewuserfiles_values.add((user_id, review.id, changeset_id, file_id))

    for file_id, file_users in watchers.items():
        for user_id, user_changesets in file_users.items():
            if user_id:
                if user_id not in reviewusers:
                    new_watchers.add(user_id)
                    reviewusers.add(user_id)
                    reviewusers_values.add((review.id, user_id))

    new_reviewers -= old_reviewers
    new_watchers -= old_reviewers | new_reviewers

    cursor.executemany("INSERT INTO reviewusers (review, uid) VALUES (%s, %s)", reviewusers_values)
    cursor.executemany("INSERT INTO reviewuserfiles (file, uid) SELECT id, %s FROM reviewfiles WHERE review=%s AND changeset=%s AND file=%s", reviewuserfiles_values)

    return new_reviewers, new_watchers

def addCommitsToReview(db, user, review, commits, new_review=False, commitset=None, pending_mails=None, silent_if_empty=set(), full_merges=set(), tracked_branch=False):
    cursor = db.cursor()

    if not new_review:
        import index

        new_commits = log_commitset.CommitSet(commits)
        old_commits = log_commitset.CommitSet(review.branch.commits)
        merges = new_commits.getMerges()

        for merge in merges:
            # We might have stripped it in a previous pass.
            if not merge in new_commits: continue

            tails = filter(lambda sha1: sha1 not in old_commits and sha1 not in merge.parents, new_commits.getTailsFrom(merge))

            if tails:
                if tracked_branch:
                    raise index.IndexException, """\
Merge %s adds merged-in commits.  Please push the merge manually
and follow the instructions.""" % merge.sha1[:8]

                cursor.execute("SELECT id, confirmed, tail FROM reviewmergeconfirmations WHERE review=%s AND uid=%s AND merge=%s", (review.id, user.id, merge.getId(db)))

                row = cursor.fetchone()

                if not row or not row[1]:
                    if not row:
                        cursor.execute("INSERT INTO reviewmergeconfirmations (review, uid, merge) VALUES (%s, %s, %s) RETURNING id", (review.id, user.id, merge.getId(db)))
                        confirmation_id = cursor.fetchone()[0]

                        merged = set()

                        for tail_sha1 in tails:
                            children = new_commits.getChildren(tail_sha1)

                            while children:
                                child = children.pop()
                                if child not in merged and new_commits.isAncestorOf(child, merge):
                                    merged.add(child)
                                    children.update(new_commits.getChildren(child) - merged)

                        merged_values = [(confirmation_id, commit.getId(db)) for commit in merged]
                        cursor.executemany("INSERT INTO reviewmergecontributions (id, merged) VALUES (%s, %s)", merged_values)
                        db.commit()
                    else:
                        confirmation_id = row[0]

                    message = "Merge %s adds merged-in commits:" % merge.sha1[:8]

                    for tail_sha1 in tails:
                        for parent_sha1 in merge.parents:
                            if parent_sha1 in new_commits:
                                parent = new_commits.get(parent_sha1)
                                if tail_sha1 in new_commits.getTailsFrom(parent):
                                    message += "\n  %s..%s" % (tail_sha1[:8], parent_sha1[:8])

                    message += """
Please confirm that this is intended by loading:
  %s/confirmmerge?id=%d""" % (dbutils.getURLPrefix(db), confirmation_id)

                    raise index.IndexException, message
                elif row[2] is not None:
                    if row[2] == merge.getId(db):
                        cursor.execute("SELECT merged FROM reviewmergecontributions WHERE id=%s",
                                       (row[0],))

                        for (merged_id,) in cursor:
                            merged = gitutils.Commit.fromId(db, review.repository, merged_id)
                            if merged.sha1 in merge.parents:
                                new_commits = new_commits.without([merged])
                                break
                    else:
                        tail = gitutils.Commit.fromId(db, review.repository, row[2])
                        cut = [gitutils.Commit.fromSHA1(db, review.repository, sha1)
                               for sha1 in tail.parents if sha1 in new_commits]
                        new_commits = new_commits.without(cut)

        if commitset:
            commitset &= set(new_commits)
            commits = [commit for commit in commits if commit in commitset]

    changesets = []
    silent_changesets = set()

    simple_commits = []
    for commit in commits:
        if commit not in full_merges:
            simple_commits.append(commit)
    if simple_commits:
        changeset_utils.createChangesets(db, review.repository, simple_commits)

    for commit in commits:
        if commit in full_merges: commit_changesets = changeset_utils.createFullMergeChangeset(db, user, review.repository, commit)
        else: commit_changesets = changeset_utils.createChangeset(db, user, review.repository, commit)

        if commit in silent_if_empty:
            for commit_changeset in commit_changesets:
                if commit_changeset.files:
                    break
            else:
                silent_changesets.update(commit_changesets)

        changesets.extend(commit_changesets)

    if not new_review:
        print "Adding %d commit%s to the review at:\n  %s" % (len(commits), len(commits) > 1 and "s" or "", review.getURL(db))

    reviewchangesets_values = [(review.id, changeset.id) for changeset in changesets]

    cursor.executemany("""INSERT INTO reviewchangesets (review, changeset) VALUES (%s, %s)""", reviewchangesets_values)
    cursor.executemany("""INSERT INTO reviewfiles (review, changeset, file, deleted, inserted)
                               SELECT reviewchangesets.review, reviewchangesets.changeset, fileversions.file, COALESCE(SUM(chunks.deleteCount), 0), COALESCE(SUM(chunks.insertCount), 0)
                                 FROM reviewchangesets
                                 JOIN fileversions USING (changeset)
                      LEFT OUTER JOIN chunks USING (changeset, file)
                                WHERE reviewchangesets.review=%s
                                  AND reviewchangesets.changeset=%s
                             GROUP BY reviewchangesets.review, reviewchangesets.changeset, fileversions.file""",
                       reviewchangesets_values)

    new_reviewers, new_watchers = assignChanges(db, user, review, changesets=changesets)

    cursor.execute("SELECT include FROM reviewrecipientfilters WHERE review=%s AND uid=0", (review.id,))

    try: opt_out = cursor.fetchone()[0] is True
    except: opt_out = True

    if not new_review:
        for user_id in new_reviewers:
            new_reviewuser = dbutils.User.fromId(db, user_id)
            print "Added reviewer: %s <%s>" % (new_reviewuser.fullname, new_reviewuser.email)

            if opt_out:
                # If the user has opted out from receiving e-mails about this
                # review while only watching it, clear the opt-out now that the
                # user becomes a reviewer.
                cursor.execute("DELETE FROM reviewrecipientfilters WHERE review=%s AND uid=%s AND include=FALSE", (review.id, user_id))

        for user_id in new_watchers:
            new_reviewuser = dbutils.User.fromId(db, user_id)
            print "Added watcher:  %s <%s>" % (new_reviewuser.fullname, new_reviewuser.email)

        review.incrementSerial(db)

    for changeset in changesets:
        review_comment.updateCommentChains(db, user, review, changeset)

    if pending_mails is None: pending_mails = []

    notify_changesets = filter(lambda changeset: changeset not in silent_changesets, changesets)

    if not new_review and notify_changesets:
        recipients = review.getRecipients(db)
        for to_user in recipients:
            pending_mails.extend(mail.sendReviewAddedCommits(db, user, to_user, recipients, review, notify_changesets, tracked_branch=tracked_branch))

    mail.sendPendingMails(pending_mails)

    review.reviewers.extend([User.fromId(db, user_id) for user_id in new_reviewers])

    for user_id in new_watchers:
        review.watchers[User.fromId(db, user_id)] = "automatic"

    return True

def createReview(db, user, repository, commits, branch_name, summary, description, from_branch_name=None, via_push=False, reviewfilters=None, applyfilters=True, applyparentfilters=False, recipientfilters=None):
    cursor = db.cursor()

    if via_push:
        applyparentfilters = bool(user.getPreference(db, 'review.applyUpstreamFilters'))

    branch = dbutils.Branch.fromName(db, repository, branch_name)

    if branch is not None:
        raise OperationFailure(code="branchexists",
                               title="Invalid review branch name",
                               message="""\
<p>There is already a branch named <code>%s</code> in the repository.  You have
to select a different name.</p>

<p>If you believe the existing branch was created during an earlier (failed)
attempt to create this review, you can try to delete it from the repository
using the command<p>

<pre>  git push &lt;remote&gt; :%s</pre>

<p>and then press the "Submit Review" button on this page again."""
                               % (htmlutils.htmlify(branch_name), htmlutils.htmlify(branch_name)))

    commitset = log_commitset.CommitSet(commits)

    if len(commitset.getHeads()) != 1:
        raise Exception, "invalid commit-set; multiple heads"

    head = commitset.getHeads().pop()

    if len(commitset.getTails()) != 1:
        tail_id = None
    else:
        tail_id = gitutils.Commit.fromSHA1(db, repository, commitset.getTails().pop()).getId(db)

    if not via_push:
        repository.branch(branch_name, head.sha1)

    try:
        cursor.execute("INSERT INTO branches (repository, name, head, tail, type) VALUES (%s, %s, %s, %s, 'review') RETURNING id", [repository.id, branch_name, head.getId(db), tail_id])

        branch_id = cursor.fetchone()[0]
        reachable_values = [(branch_id, commit.getId(db)) for commit in commits]

        cursor.executemany("INSERT INTO reachable (branch, commit) VALUES (%s, %s)", reachable_values)

        cursor.execute("INSERT INTO reviews (type, branch, state, summary, description, applyfilters, applyparentfilters) VALUES ('official', %s, 'open', %s, %s, %s, %s) RETURNING id", (branch_id, summary, description, applyfilters, applyparentfilters))

        review = dbutils.Review.fromId(db, cursor.fetchone()[0])

        cursor.execute("INSERT INTO reviewusers (review, uid, owner) VALUES (%s, %s, TRUE)", (review.id, user.id))

        if reviewfilters is not None:
            cursor.executemany("INSERT INTO reviewfilters (review, uid, directory, file, type, creator) VALUES (%s, %s, %s, %s, %s, %s)",
                               [(review.id, filter_user_id, filter_directory_id, filter_file_id, filter_type, user.id)
                                for filter_directory_id, filter_file_id, filter_type, filter_delegate, filter_user_id in reviewfilters])

        if recipientfilters is not None:
            cursor.executemany("INSERT INTO reviewrecipientfilters (review, uid, include) VALUES (%s, %s, %s)",
                               [(review.id, filter_user_id, filter_include)
                                for filter_user_id, filter_include in recipientfilters])

        addCommitsToReview(db, user, review, commits, new_review=True)

        if from_branch_name is not None:
            cursor.execute("UPDATE branches SET review=%s WHERE repository=%s AND name=%s", (review.id, repository.id, from_branch_name))

        # Reload to get list of changesets added by addCommitsToReview().
        review = dbutils.Review.fromId(db, review.id)

        pending_mails = []
        recipients = review.getRecipients(db)
        for to_user in recipients:
            pending_mails.extend(mail.sendReviewCreated(db, user, to_user, recipients, review))

        db.commit()

        mail.sendPendingMails(pending_mails)

        return review
    except:
        if not via_push:
            repository.run("branch", "-D", branch_name)
        raise

def countDraftItems(db, user, review):
    cursor = db.cursor()

    cursor.execute("SELECT reviewfilechanges.to, SUM(deleted) + SUM(inserted) FROM reviewfiles JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id) WHERE reviewfiles.review=%s AND reviewfilechanges.uid=%s AND reviewfilechanges.state='draft' GROUP BY reviewfilechanges.to", (review.id, user.id))

    reviewed = unreviewed = 0

    for to_state, lines in cursor:
        if to_state == "reviewed": reviewed = lines
        else: unreviewed = lines

    cursor.execute("SELECT reviewfilechanges.to, COUNT(*) FROM reviewfiles JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id) WHERE reviewfiles.review=%s AND reviewfiles.deleted=0 AND reviewfiles.inserted=0 AND reviewfilechanges.uid=%s AND reviewfilechanges.state='draft' GROUP BY reviewfilechanges.to", (review.id, user.id))

    reviewedBinary = unreviewedBinary = 0

    for to_state, lines in cursor:
        if to_state == "reviewed": reviewedBinary = lines
        else: unreviewedBinary = lines

    cursor.execute("SELECT count(*) FROM commentchains, comments WHERE commentchains.review=%s AND comments.chain=commentchains.id AND comments.uid=%s AND comments.state='draft'", [review.id, user.id])
    comments = cursor.fetchone()[0]

    cursor.execute("""SELECT count(*) FROM commentchains, commentchainchanges
                       WHERE commentchains.review=%s
                         AND commentchains.state=commentchainchanges.from_state
                         AND commentchainchanges.chain=commentchains.id
                         AND commentchainchanges.uid=%s
                         AND commentchainchanges.state='draft'
                         AND (commentchainchanges.from_state='addressed' OR commentchainchanges.from_state='closed')
                         AND commentchainchanges.to_state='open'""",
                   [review.id, user.id])
    reopened = cursor.fetchone()[0]

    cursor.execute("""SELECT count(*) FROM commentchains, commentchainchanges
                       WHERE commentchains.review=%s
                         AND commentchains.state='open'
                         AND commentchainchanges.chain=commentchains.id
                         AND commentchainchanges.uid=%s
                         AND commentchainchanges.state='draft'
                         AND commentchainchanges.from_state='open'
                         AND commentchainchanges.to_state='closed'""",
                   [review.id, user.id])
    closed = cursor.fetchone()[0]

    cursor.execute("""SELECT count(*) FROM commentchains, commentchainchanges
                       WHERE commentchains.review=%s
                         AND commentchainchanges.chain=commentchains.id
                         AND commentchainchanges.uid=%s
                         AND commentchainchanges.state='draft'
                         AND commentchainchanges.from_type=commentchains.type
                         AND commentchainchanges.to_type!=commentchains.type""",
                   [review.id, user.id])
    morphed = cursor.fetchone()[0]

    return { "reviewedNormal": reviewed,
             "unreviewedNormal": unreviewed,
             "reviewedBinary": reviewedBinary,
             "unreviewedBinary": unreviewedBinary,
             "writtenComments": comments,
             "reopenedIssues": reopened,
             "resolvedIssues": closed,
             "morphedChains": morphed }

def getDraftItems(db, user, review):
    return "approved=%(reviewedNormal)d,disapproved=%(unreviewedNormal)d,approvedBinary=%(reviewedBinary)d,disapprovedBinary=%(unreviewedBinary)d,comments=%(writtenComments)d,reopened=%(reopenedIssues)d,closed=%(resolvedIssues)d,morphed=%(morphedChains)d" % review.getDraftStatus(db, user)

def renderDraftItems(db, user, review, target):
    items = review.getDraftStatus(db, user)

    target.addExternalStylesheet("resource/review.css")
    target.addExternalScript("resource/review.js")

    div = target.div(id='draftStatus')

    if any(items.values()):
        div.span('draft').text("Draft: ")

        approved = items.pop("reviewedNormal", None)
        if approved:
            div.text(' ')
            div.span('approved').text("reviewed %d line%s" % (approved, approved > 1 and "s" or ""))

            if any(items.values()): div.text(',')

        disapproved = items.pop("unreviewedNormal", None)
        if disapproved:
            div.text(' ')
            div.span('disapproved').text("unreviewed %d line%s" % (disapproved, disapproved > 1 and "s" or ""))

            if any(items.values()): div.text(',')

        approved = items.pop("reviewedBinary", None)
        if approved:
            div.text(' ')
            div.span('approved-binary').text("reviewed %d binary file%s" % (approved, approved > 1 and "s" or ""))

            if any(items.values()): div.text(',')

        disapproved = items.pop("unreviewedBinary", None)
        if disapproved:
            div.text(' ')
            div.span('disapproved-binary').text("unreviewed %d binary file%s" % (disapproved, disapproved > 1 and "s" or ""))

            if any(items.values()): div.text(',')

        comments = items.pop("writtenComments", None)
        if comments:
            div.text(' ')
            div.span('comments').text("wrote %d comment%s" % (comments, comments > 1 and "s" or ""))

            if any(items.values()): div.text(',')

        reopened = items.pop("reopenedIssues", None)
        if reopened:
            div.text(' ')
            div.span('reopened').text("reopened %d issue%s" % (reopened, reopened > 1 and "s" or ""))

            if any(items.values()): div.text(',')

        closed = items.pop("resolvedIssues", None)
        if closed:
            div.text(' ')
            div.span('closed').text("resolved %d issue%s" % (closed, closed > 1 and "s" or ""))

            if any(items.values()): div.text(',')

        morphed = items.pop("morphedChains", None)
        if morphed:
            div.text(' ')
            div.span('closed').text("morphed %d comment%s" % (morphed, morphed > 1 and "s" or ""))

            if any(items.values()): div.text(',')

        div.text(' ')
        buttons = div.span("buttons")
        buttons.button(onclick='previewChanges();').text("Preview")
        buttons.button(onclick='submitChanges();').text("Submit")
        buttons.button(onclick='cancelChanges();').text("Abort")

        return True
    else:
        return False

def addReviewFilters(db, creator, user, review, reviewer_directory_ids, reviewer_file_ids, watcher_directory_ids, watcher_file_ids):
    cursor = db.cursor()

    cursor.execute("INSERT INTO reviewassignmentstransactions (review, assigner) VALUES (%s, %s) RETURNING id", (review.id, creator.id))
    transaction_id = cursor.fetchone()[0]

    def add(filter_type, directory_ids, file_ids):
        for directory_id, file_id in izip(directory_ids, file_ids):
            cursor.execute("""SELECT id, type
                                FROM reviewfilters
                               WHERE review=%s
                                 AND uid=%s
                                 AND directory=%s
                                 AND file=%s""",
                           (review.id, user.id, directory_id, file_id))

            row = cursor.fetchone()

            if row:
                old_filter_id, old_filter_type = row

                if old_filter_type == filter_type:
                    continue
                else:
                    cursor.execute("""DELETE FROM reviewfilters
                                            WHERE id=%s""",
                                   (old_filter_id,))
                    cursor.execute("""INSERT INTO reviewfilterchanges (transaction, uid, directory, file, type, created)
                                           VALUES (%s, %s, %s, %s, %s, false)""",
                                   (transaction_id, user.id, directory_id, file_id, old_filter_type))

            cursor.execute("""INSERT INTO reviewfilters (review, uid, directory, file, type, creator)
                                   VALUES (%s, %s, %s, %s, %s, %s)""",
                           (review.id, user.id, directory_id, file_id, filter_type, creator.id))
            cursor.execute("""INSERT INTO reviewfilterchanges (transaction, uid, directory, file, type, created)
                                   VALUES (%s, %s, %s, %s, %s, true)""",
                           (transaction_id, user.id, directory_id, file_id, filter_type))

    add("reviewer", reviewer_directory_ids, repeat(0))
    add("reviewer", repeat(0), reviewer_file_ids)
    add("watcher", watcher_directory_ids, repeat(0))
    add("watcher", repeat(0), watcher_file_ids)

    filters = Filters()
    filters.load(db, review=review, user=user)

    if user not in review.reviewers and user not in review.watchers and user not in review.owners:
        cursor.execute("""INSERT INTO reviewusers (review, uid, type)
                          VALUES (%s, %s, 'manual')""",
                       (review.id, user.id,))

    delete_files = set()
    insert_files = set()

    if watcher_directory_ids or watcher_file_ids:
        # Unassign changes currently assigned to the affected user.
        cursor.execute("""SELECT reviewfiles.id, reviewfiles.file
                            FROM reviewfiles
                            JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                           WHERE reviewfiles.review=%s
                             AND reviewuserfiles.uid=%s""",
                       (review.id, user.id))

        for review_file_id, file_id in cursor:
            if not filters.isReviewer(db, user.id, file_id):
                delete_files.add(review_file_id)

    if reviewer_directory_ids or reviewer_file_ids:
        # Assign changes currently not assigned to the affected user.
        cursor.execute("""SELECT reviewfiles.id, reviewfiles.file
                            FROM reviewfiles
                            JOIN changesets ON (changesets.id=reviewfiles.changeset)
                            JOIN commits ON (commits.id=changesets.child)
                            JOIN gitusers ON (gitusers.id=commits.author_gituser)
                 LEFT OUTER JOIN usergitemails USING (email)
                 LEFT OUTER JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id AND reviewuserfiles.uid=%s)
                           WHERE reviewfiles.review=%s
                             AND (usergitemails.uid IS NULL OR usergitemails.uid!=%s)
                             AND reviewuserfiles.uid IS NULL""",
                       (user.id, review.id, user.id))

        for review_file_id, file_id in cursor:
            if filters.isReviewer(db, user.id, file_id):
                insert_files.add(review_file_id)

    if delete_files:
        cursor.executemany("DELETE FROM reviewuserfiles WHERE file=%s AND uid=%s",
                           izip(delete_files, repeat(user.id)))
        cursor.executemany("INSERT INTO reviewassignmentchanges (transaction, file, uid, assigned) VALUES (%s, %s, %s, false)",
                           izip(repeat(transaction_id), delete_files, repeat(user.id)))

    if insert_files:
        cursor.executemany("INSERT INTO reviewuserfiles (file, uid) VALUES (%s, %s)",
                           izip(insert_files, repeat(user.id)))
        cursor.executemany("INSERT INTO reviewassignmentchanges (transaction, file, uid, assigned) VALUES (%s, %s, %s, true)",
                           izip(repeat(transaction_id), insert_files, repeat(user.id)))

    return generateMailsForAssignmentsTransaction(db, transaction_id)

def parseReviewFilters(db, data):
    reviewfilters = []

    for filter_data in data:
        filter_username = filter_data["username"]
        filter_type = filter_data["type"]
        filter_path = filter_data["path"]

        filter_user = dbutils.User.fromName(db, filter_username)
        if not filter_user:
            raise OperationError("no such user: '%s'" % filter_username)

        filter_directory_id = 0
        filter_file_id = 0

        if filter_path != "/":
            if filter_path[-1] == "/" or dbutils.is_directory(filter_path):
                filter_directory_id = dbutils.find_directory(db, path=filter_path)
            else:
                filter_file_id = dbutils.find_file(db, path=filter_path)

        reviewfilters.append((filter_directory_id, filter_file_id, filter_type, None, filter_user.id))

    return reviewfilters

def parseRecipientFilters(db, data):
    mode = data.get("mode", "opt-out")
    included = data.get("included", [])
    excluded = data.get("excluded", [])

    recipientfilters = []

    if mode == "opt-in":
        recipientfilters.append((0, False))
        filter_usernames = included
        filter_include = True
    else:
        filter_usernames = excluded
        filter_include = False

    for filter_username in filter_usernames:
        filter_user = dbutils.User.fromName(db, filter_username)
        if not filter_user:
            raise OperationError("no such user: '%s'" % filter_username)
        recipientfilters.append((filter_user.id, filter_include))

    return recipientfilters

def queryParentFilters(db, user, review):
    assert review.applyfilters
    assert not review.applyparentfilters

    cursor = db.cursor()

    cursor.execute("UPDATE reviews SET applyparentfilters=TRUE WHERE id=%s", (review.id,))
    review.applyparentfilters = True

    review.branch.loadCommits(db)

    return assignChanges(db, user, review, commits=review.branch.commits, update=True, parentfiltersonly=True)

def applyParentFilters(db, user, review):
    assert review.applyfilters
    assert not review.applyparentfilters

    cursor = db.cursor()

    cursor.execute("UPDATE reviews SET applyparentfilters=TRUE WHERE id=%s", (review.id,))
    review.applyparentfilters = True

    review.branch.loadCommits(db)

    new_reviewers, new_watchers = assignChanges(db, user, review, commits=review.branch.commits, update=True, parentfiltersonly=True)

    pending_mails = []

    for user_id in new_reviewers:
        new_reviewer = dbutils.User.fromId(db, user_id)

        cursor.execute("""SELECT reviewfiles.file, SUM(reviewfiles.deleted), SUM(reviewfiles.inserted)
                            FROM reviewfiles
                            JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                           WHERE reviewfiles.review=%s
                             AND reviewuserfiles.uid=%s
                        GROUP BY reviewfiles.file""",
                       (review.id, user_id))

        pending_mails.extend(mail.sendParentFiltersApplied(db, user, new_reviewer, review, cursor.fetchall()))

    for user_id in new_watchers:
        new_watcher = dbutils.User.fromId(db, user_id)
        pending_mails.extend(mail.sendParentFiltersApplied(db, user, new_watcher, review, None))

    db.commit()

    mail.sendPendingMails(pending_mails)

def generateMailsForBatch(db, batch_id, was_accepted, is_accepted, profiler=None):
    cursor = db.cursor()
    cursor.execute("SELECT review, uid FROM batches WHERE id=%s", (batch_id,))

    review_id, user_id = cursor.fetchone()

    review = dbutils.Review.fromId(db, review_id)
    from_user = dbutils.User.fromId(db, user_id)

    pending_mails = []

    recipients = review.getRecipients(db)
    for to_user in recipients:
        pending_mails.extend(mail.sendReviewBatch(db, from_user, to_user, recipients, review, batch_id, was_accepted, is_accepted, profiler=profiler))

    return pending_mails

def generateMailsForAssignmentsTransaction(db, transaction_id):
    cursor = db.cursor()
    cursor.execute("SELECT review, assigner, note FROM reviewassignmentstransactions WHERE id=%s", (transaction_id,))

    review_id, assigner_id, note = cursor.fetchone()

    review = dbutils.Review.fromId(db, review_id)
    assigner = dbutils.User.fromId(db, assigner_id)

    cursor.execute("""SELECT uid, directory, file, type, created
                        FROM reviewfilterchanges
                       WHERE transaction=%s""",
                   (transaction_id,))

    by_user = {}

    for reviewer_id, directory_id, file_id, filter_type, created in cursor:
        added_filters, removed_filters, unassigned, assigned = by_user.setdefault(reviewer_id, ([], [], [], []))

        if file_id: path = dbutils.describe_file(db, file_id)
        elif directory_id: path = dbutils.describe_directory(db, directory_id)
        else: path = "/"

        if created: added_filters.append((filter_type, path))
        else: removed_filters.append((filter_type, path))

    cursor.execute("""SELECT reviewassignmentchanges.uid, reviewassignmentchanges.assigned, reviewfiles.file, SUM(reviewfiles.deleted), SUM(reviewfiles.inserted)
                        FROM reviewfiles
                        JOIN reviewassignmentchanges ON (reviewassignmentchanges.file=reviewfiles.id)
                       WHERE reviewassignmentchanges.transaction=%s
                    GROUP BY reviewassignmentchanges.uid, reviewassignmentchanges.assigned, reviewfiles.file""",
                   (transaction_id,))

    for reviewer_id, was_assigned, file_id, deleted, inserted in cursor:
        added_filters, removed_filters, unassigned, assigned = by_user.setdefault(reviewer_id, (None, None, [], []))

        if was_assigned: assigned.append((file_id, deleted, inserted))
        else: unassigned.append((file_id, deleted, inserted))

    pending_mails = []

    for reviewer_id, (added_filters, removed_filters, unassigned, assigned) in by_user.items():
        reviewer = dbutils.User.fromId(db, reviewer_id)
        if assigner != reviewer:
            pending_mails.extend(mail.sendAssignmentsChanged(db, assigner, reviewer, review, added_filters, removed_filters, unassigned, assigned))

    return pending_mails

def retireUser(db, user):
    cursor = db.cursor()

    # Set the user's status to 'retired'.
    cursor.execute("""UPDATE users
                         SET status='retired'
                       WHERE id=%s""",
                   (user.id,))

    # Delete any assignments of unreviewed (pending) changes to the user.  We're
    # leaving assignments of reviewed changes in-place; no particular need to
    # drop historical data.
    #
    # Deleting even this risks dropping some historical data, specifically
    # changes involving files being marked as reviewed, and then unmarked again.
    # But having "active" assignments to users that aren't going to review them
    # complicates a whole bunch of queries, so to keep things simple, we can
    # sacrifice a little history.
    cursor.execute("""DELETE FROM reviewuserfiles
                            USING reviewfiles
                            WHERE reviewuserfiles.uid=%s
                              AND reviewuserfiles.file=reviewfiles.id
                              AND reviewfiles.state='pending'""",
                   (user.id,))
