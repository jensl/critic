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
import gitutils
from dbutils import *
from itertools import izip, repeat, chain
import htmlutils
import configuration

from . import mail
import diff
import changeset.utils as changeset_utils
import changeset.load as changeset_load
import reviewing.comment
import reviewing.filters
import log.commitset as log_commitset
import extensions.role.filterhook
import background.utils

from operation import OperationError, OperationFailure
from .filters import Filters

def getFileIdsFromChangesets(changesets):
    file_ids = set()
    for changeset in changesets:
        file_ids.update(changed_file.id for changed_file in changeset.files)
    return file_ids

def getReviewersAndWatchers(db, repository, commits=None, changesets=None, reviewfilters=None,
                            applyfilters=True, applyparentfilters=False):
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

    cursor = db.readonly_cursor()

    filters = Filters()
    filters.setFiles(db, list(getFileIdsFromChangesets(changesets)))

    if applyfilters:
        filters.load(db, repository=repository, recursive=applyparentfilters)

    if reviewfilters:
        filters.addFilters(reviewfilters)

    reviewers = {}
    watchers = {}

    for changeset in changesets:
        author_user_ids = changeset.child.author.getUserIds(db) if changeset.child else set()

        cursor.execute("SELECT DISTINCT file FROM fileversions WHERE changeset=%s", (changeset.id,))

        for (file_id,) in cursor:
            reviewers_found = False

            for user_id, (filter_type, delegate) in filters.listUsers(file_id).items():
                if filter_type == 'reviewer':
                    if user_id not in author_user_ids:
                        reviewer_user_ids = [user_id]
                    elif delegate:
                        reviewer_user_ids = []
                        for delegate_user_name in delegate.split(","):
                            delegate_user = dbutils.User.fromName(db, delegate_user_name)
                            reviewer_user_ids.append(delegate_user.id)
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

    cursor = db.readonly_cursor()

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

    cursor = db.readonly_cursor()

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

def assignChanges(db, user, review, commits=None, changesets=None, update=False):
    if changesets is None:
        assert commits is not None

        changesets = []

        for commit in commits:
            changesets.extend(changeset_utils.createChangeset(db, user, review.repository, commit))

    applyfilters = review.applyfilters
    applyparentfilters = review.applyparentfilters

    reviewers, watchers = getReviewersAndWatchers(db, review.repository, changesets=changesets, reviewfilters=review.getReviewFilters(db),
                                                  applyfilters=applyfilters, applyparentfilters=applyparentfilters)

    cursor = db.readonly_cursor()
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

    with db.updating_cursor("reviewusers",
                            "reviewuserfiles") as cursor:
        cursor.executemany(
            """INSERT INTO reviewusers (review, uid)
                    VALUES (%s, %s)""",
            reviewusers_values)
        cursor.executemany(
            """INSERT INTO reviewuserfiles (file, uid)
                    SELECT id, %s
                      FROM reviewfiles
                     WHERE review=%s
                       AND changeset=%s
                       AND file=%s""",
            reviewuserfiles_values)

    if configuration.extensions.ENABLED:
        cursor = db.readonly_cursor()
        cursor.execute("""SELECT id, uid, extension, path
                            FROM extensionhookfilters
                           WHERE repository=%s""",
                       (review.repository.id,))

        rows = cursor.fetchall()

        if rows:
            if commits is None:
                commits = set()
                for changeset in changesets:
                    commits.add(changeset.child)
                commits = list(commits)

            filters = Filters()
            filters.setFiles(db, list(getFileIdsFromChangesets(changesets)))

            for filter_id, user_id, extension_id, path in rows:
                filters.addFilter(user_id, path, None, None, filter_id)

            for filter_id, file_ids in filters.matched_files.items():
                extensions.role.filterhook.queueFilterHookEvent(
                    db, filter_id, review, user, commits, file_ids)

    return new_reviewers, new_watchers

def prepareChangesetsForCommits(db, commits, silent_if_empty, full_merges, replayed_rebases):
    repository = commits[0].repository
    simple_commits = []

    for commit in commits:
        if commit not in full_merges and commit not in replayed_rebases:
            simple_commits.append(commit)

    if simple_commits:
        changeset_utils.createChangesets(db, repository, simple_commits)

    for commit in commits:
        if commit in full_merges:
            changeset_utils.createFullMergeChangeset(
                db, user, repository, commit, do_highlight=False)
        elif commit in replayed_rebases:
            changeset_utils.createChangeset(
                db, user, repository,
                from_commit=commit, to_commit=replayed_rebases[commit],
                conflicts=True, do_highlight=False)

def createChangesetsForCommits(db, commits, silent_if_empty, full_merges, replayed_rebases):
    repository = commits[0].repository
    changesets = []
    silent_commits = set()
    silent_changesets = set()

    for commit in commits:
        if commit in full_merges:
            commit_changesets = changeset_utils.createFullMergeChangeset(
                db, user, repository, commit, do_highlight=False)
        elif commit in replayed_rebases:
            commit_changesets = changeset_utils.createChangeset(
                db, user, repository,
                from_commit=commit, to_commit=replayed_rebases[commit],
                conflicts=True, do_highlight=False)
        else:
            commit_changesets = changeset_utils.createChangeset(
                db, user, repository, commit, do_highlight=False)

        if commit in silent_if_empty:
            for commit_changeset in commit_changesets:
                if commit_changeset.files:
                    break
            else:
                silent_commits.add(commit)
                silent_changesets.update(commit_changesets)

        changesets.extend(commit_changesets)

    return changesets, silent_commits, silent_changesets

def addCommitsToReview(db, user, review, previous_head, commits, new_review,
                       branchupdate_id, silent_if_empty=set(),
                       full_merges=set(), replayed_rebases={},
                       tracked_branch=False):
    changesets, silent_commits, silent_changesets = \
        createChangesetsForCommits(db, commits, silent_if_empty, full_merges, replayed_rebases)

    reviewchangesets_values = [(review.id, branchupdate_id, changeset.id)
                               for changeset in changesets]
    reviewfiles_values = [(review.id, changeset.id)
                          for changeset in changesets]

    with db.updating_cursor("reviewchangesets",
                            "reviewfiles",
                            "reviewusers",
                            "reviewuserfiles",
                            # Updated indirectly via assignChanges().
                            "extensionfilterhookevents",
                            "extensionfilterhookcommits",
                            "extensionfilterhookfiles") as cursor:
        cursor.executemany(
            """INSERT INTO reviewchangesets (review, branchupdate, changeset)
                    VALUES (%s, %s, %s)""",
            reviewchangesets_values)
        cursor.executemany(
            """INSERT INTO reviewfiles (review, changeset, file, deleted, inserted)
                    SELECT reviewchangesets.review, reviewchangesets.changeset,
                           fileversions.file, COALESCE(SUM(chunks.deleteCount), 0),
                           COALESCE(SUM(chunks.insertCount), 0)
                      FROM reviewchangesets
                      JOIN fileversions USING (changeset)
           LEFT OUTER JOIN chunks USING (changeset, file)
                     WHERE reviewchangesets.review=%s
                       AND reviewchangesets.changeset=%s
                  GROUP BY reviewchangesets.review, reviewchangesets.changeset,
                           fileversions.file""",
            reviewfiles_values)

        new_reviewers, new_watchers = assignChanges(db, user, review, changesets=changesets)

    cursor = db.readonly_cursor()
    cursor.execute("SELECT include FROM reviewrecipientfilters WHERE review=%s AND uid IS NULL", (review.id,))

    try: opt_out = cursor.fetchone()[0] is True
    except: opt_out = True

    output = ""

    reviewrecipientfilters_values = []

    if new_reviewers:
        output += ("Added reviewer%s:\n"
                   % ("s" if len(new_reviewers) > 1 else ""))

        for user_id in new_reviewers:
            new_reviewuser = dbutils.User.fromId(db, user_id)
            output += "  %s <%s>\n" % (new_reviewuser.fullname,
                                       new_reviewuser.email)

            if not new_review and opt_out:
                # If the user has opted out from receiving e-mails about this
                # review while only watching it, clear the opt-out now that the
                # user becomes a reviewer.
                reviewrecipientfilters_values.append((review.id, user_id))

        output += "\n"
    elif new_review:
        output += "No reviewers were added.\n\n"

    if reviewrecipientfilters_values:
        with db.updating_cursor("reviewrecipientfilters") as cursor:
            cursor.executemany(
                """DELETE
                     FROM reviewrecipientfilters
                    WHERE review=%s
                      AND uid=%s
                      AND NOT include""",
                reviewrecipientfilters_values)

    if new_watchers:
        output += ("Added watcher%s:\n"
                   % ("s" if len(new_reviewers) > 1 else ""))

        for user_id in new_watchers:
            new_reviewuser = dbutils.User.fromId(db, user_id)
            output += "  %s <%s>\n" % (new_reviewuser.fullname,
                                       new_reviewuser.email)

        output += "\n"

    if not new_review:
        review.incrementSerial(db)

        output += reviewing.comment.propagateCommentChains(
            db, user, review, previous_head, log_commitset.CommitSet(commits),
            replayed_rebases)

    notify_commits = filter(lambda commit: commit not in silent_commits, commits)
    notify_changesets = filter(lambda changeset: changeset not in silent_changesets, changesets)

    recipients = review.getRecipients(db)

    if new_review:
        for to_user in recipients:
            db.pending_mails.extend(mail.sendReviewCreated(
                db, user, to_user, recipients, review))
    elif notify_changesets:
        for to_user in recipients:
            db.pending_mails.extend(mail.sendReviewAddedCommits(
                db, user, to_user, recipients, review, notify_commits,
                notify_changesets, tracked_branch=tracked_branch))

    review.reviewers.extend([User.fromId(db, user_id) for user_id in new_reviewers])

    for user_id in new_watchers:
        review.watchers[User.fromId(db, user_id)] = "automatic"

    return output

def createReview(db, user, repository, commits, branch_name, summary, description, from_branch_name=None, via_push=False, reviewfilters=None, applyfilters=True, applyparentfilters=False, recipientfilters=None, pendingrefupdate_id=None):
    cursor = db.cursor()

    if via_push:
        applyparentfilters = bool(user.getPreference(db, 'review.applyUpstreamFilters'))

    branch = dbutils.Branch.fromName(db, repository, branch_name)

    if branch is not None:
        raise OperationFailure(
            code="branchexists",
            title="Invalid review branch name",
            message="""\
<p>There is already a branch named <code>%s</code> in the repository.  You have
to select a different name.</p>

<p>If you believe the existing branch was created during an earlier (failed)
attempt to create this review, you can try to delete it from the repository
using the command<p>

<pre>  git push &lt;remote&gt; :%s</pre>

<p>and then press the "Submit Review" button on this page again."""
            % (htmlutils.htmlify(branch_name), htmlutils.htmlify(branch_name)),
            is_html=True)

    if not commits:
        raise OperationFailure(
            code="nocommits",
            title="No commits specified",
            message="You need at least one commit to create a review.")

    commitset = log_commitset.CommitSet(commits)
    heads = commitset.getHeads()

    if len(heads) != 1:
        # There is really no plausible way for this error to occur.
        raise OperationFailure(
            code="disconnectedtree",
            title="Disconnected tree",
            message=("The specified commits do do not form a single connected "
                     "tree.  Creating a review of them is not supported."))

    head = heads.pop()

    if len(commitset.getTails()) != 1:
        tail_id = None
    else:
        tail_id = gitutils.Commit.fromSHA1(db, repository, commitset.getTails().pop()).getId(db)

    if not via_push:
        try:
            repository.createBranch(branch_name, head.sha1)
        except gitutils.GitCommandError as error:
            raise OperationFailure(
                code="branchfailed",
                title="Failed to create review branch",
                message=("<p><b>Output from git:</b></p>"
                         "<code style='padding-left: 1em'>%s</code>"
                         % htmlutils.htmlify(error.output)),
                is_html=True)

    try:
        branch_id = dbutils.Branch.insert(
            db, repository, user, branch_name, 'review', None, head.getId(db),
            tail_id, None, commits, pendingrefupdate_id)

        from_branch_id = None
        if from_branch_name is not None:
            cursor.execute("""SELECT id
                                FROM branches
                               WHERE repository=%s
                                 AND name=%s""",
                           (repository.id, from_branch_name))
            row = cursor.fetchone()
            if row:
                from_branch_id = row[0]

        cursor.execute("""INSERT INTO reviews (type, branch, origin, state,
                                               summary, description,
                                               applyfilters, applyparentfilters)
                               VALUES ('official', %s, %s, 'open',
                                       %s, %s,
                                       %s, %s)
                            RETURNING id""",
                       (branch_id, from_branch_id,
                        summary, description,
                        applyfilters, applyparentfilters))

        review = dbutils.Review.fromId(db, cursor.fetchone()[0])

        cursor.execute("""INSERT INTO reviewusers (review, uid, owner)
                               VALUES (%s, %s, TRUE)""",
                       (review.id, user.id))

        if reviewfilters is not None:
            cursor.executemany("""INSERT INTO reviewfilters (review, uid, path, type, creator)
                                       VALUES (%s, %s, %s, %s, %s)""",
                               [(review.id, filter_user_id, filter_path, filter_type, user.id)
                                for filter_user_id, filter_path, filter_type, filter_delegate in reviewfilters])

        # is_opt_in = False

        if recipientfilters is not None:
            cursor.executemany(
                """INSERT INTO reviewrecipientfilters (review, uid, include)
                        VALUES (%s, %s, %s)""",
                [(review.id, filter_user_id, filter_include)
                 for filter_user_id, filter_include in recipientfilters])

            # for filter_user_id, filter_include in recipientfilters:
            #     if filter_user_id is None and not filter_include:
            #         is_opt_in = True

        db.commit()

        # Wake the review updater up to do the heavy lifting.
        background.utils.wakeup(configuration.services.REVIEWUPDATER)

        return review
    except:
        if not via_push:
            repository.run("branch", "-D", branch_name)
        raise

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

def addReviewFilters(db, creator, user, review, reviewer_paths, watcher_paths):
    cursor = db.cursor()
    cursor.execute("INSERT INTO reviewassignmentstransactions (review, assigner) VALUES (%s, %s) RETURNING id", (review.id, creator.id))
    transaction_id = cursor.fetchone()[0]

    def add(filter_type, paths):
        for path in paths:
            cursor.execute("""SELECT id, type
                                FROM reviewfilters
                               WHERE review=%s
                                 AND uid=%s
                                 AND path=%s""",
                           (review.id, user.id, path))

            row = cursor.fetchone()

            if row:
                old_filter_id, old_filter_type = row

                if old_filter_type == filter_type:
                    continue
                else:
                    cursor.execute("""DELETE FROM reviewfilters
                                            WHERE id=%s""",
                                   (old_filter_id,))
                    cursor.execute("""INSERT INTO reviewfilterchanges (transaction, uid, path, type, created)
                                           VALUES (%s, %s, %s, %s, false)""",
                                   (transaction_id, user.id, path, old_filter_type))

            cursor.execute("""INSERT INTO reviewfilters (review, uid, path, type, creator)
                                   VALUES (%s, %s, %s, %s, %s)""",
                           (review.id, user.id, path, filter_type, creator.id))
            cursor.execute("""INSERT INTO reviewfilterchanges (transaction, uid, path, type, created)
                                   VALUES (%s, %s, %s, %s, true)""",
                           (transaction_id, user.id, path, filter_type))

    add("reviewer", reviewer_paths)
    add("watcher", watcher_paths)

    filters = Filters()
    filters.setFiles(db, review=review)
    filters.load(db, review=review, user=user)

    if user not in review.reviewers and user not in review.watchers and user not in review.owners:
        cursor.execute("""INSERT INTO reviewusers (review, uid, type)
                          VALUES (%s, %s, 'manual')""",
                       (review.id, user.id,))

    delete_files = set()
    insert_files = set()

    if watcher_paths:
        # Unassign changes currently assigned to the affected user.
        cursor.execute("""SELECT reviewfiles.id, reviewfiles.file
                            FROM reviewfiles
                            JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                           WHERE reviewfiles.review=%s
                             AND reviewuserfiles.uid=%s""",
                       (review.id, user.id))

        for review_file_id, file_id in cursor:
            if not filters.isReviewer(user.id, file_id):
                delete_files.add(review_file_id)

    if reviewer_paths:
        # Assign changes currently not assigned to the affected user.
        cursor.execute("""SELECT reviewfiles.id, reviewfiles.file
                            FROM reviewfiles
                            JOIN changesets ON (changesets.id=reviewfiles.changeset)
                            JOIN commits ON (commits.id=changesets.child)
                            JOIN gitusers ON (gitusers.id=commits.author_gituser)
                 LEFT OUTER JOIN usergitemails ON (usergitemails.email=gitusers.email
                                               AND usergitemails.uid=%s)
                 LEFT OUTER JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id
                                                 AND reviewuserfiles.uid=%s)
                           WHERE reviewfiles.review=%s
                             AND usergitemails.uid IS NULL
                             AND reviewuserfiles.uid IS NULL""",
                       (user.id, user.id, review.id))

        for review_file_id, file_id in cursor:
            if filters.isReviewer(user.id, file_id):
                insert_files.add(review_file_id)

    if delete_files:
        cursor.executemany("DELETE FROM reviewuserfiles WHERE file=%s AND uid=%s",
                           zip(delete_files, repeat(user.id)))
        cursor.executemany("INSERT INTO reviewassignmentchanges (transaction, file, uid, assigned) VALUES (%s, %s, %s, false)",
                           zip(repeat(transaction_id), delete_files, repeat(user.id)))

    if insert_files:
        cursor.executemany("INSERT INTO reviewuserfiles (file, uid) VALUES (%s, %s)",
                           zip(insert_files, repeat(user.id)))
        cursor.executemany("INSERT INTO reviewassignmentchanges (transaction, file, uid, assigned) VALUES (%s, %s, %s, true)",
                           zip(repeat(transaction_id), insert_files, repeat(user.id)))

    generateMailsForAssignmentsTransaction(db, transaction_id)

def parseReviewFilters(db, data):
    reviewfilters = []

    for filter_data in data:
        filter_user = dbutils.User.fromName(db, filter_data["username"])
        filter_type = filter_data["type"]
        filter_path = reviewing.filters.sanitizePath(filter_data["path"])

        # Make sure the path doesn't contain any invalid wild-cards.
        try:
            reviewing.filters.validatePattern(filter_path)
        except reviewing.filters.PatternError as error:
            raise OperationFailure(code="invalidpattern",
                                   title="Invalid filter pattern",
                                   message="Problem: %s" % error.message)

        reviewfilters.append((filter_user.id, filter_path, filter_type, None))

    return reviewfilters

def parseRecipientFilters(db, data):
    mode = data.get("mode", "opt-out")
    included = data.get("included", [])
    excluded = data.get("excluded", [])

    recipientfilters = []

    if mode == "opt-in":
        recipientfilters.append((None, False))
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

def _updateFilters(db, cursor, user, review, globalfilters, parentfilters):
    if globalfilters:
        cursor.execute("UPDATE reviews SET applyfilters=TRUE WHERE id=%s", (review.id,))
        review.applyfilters = True
    if parentfilters:
        cursor.execute("UPDATE reviews SET applyparentfilters=TRUE WHERE id=%s", (review.id,))
        review.applyparentfilters = True

    cursor.execute("""SELECT changeset
                        FROM reviewchangesets
                       WHERE review=%s""",
                   (review.id,))

    # TODO: This two-phase creation of Changeset objects is a bit silly.
    changesets = [diff.Changeset.fromId(db, review.repository, changeset_id)
                  for (changeset_id,) in cursor]
    changeset_load.loadChangesets(
        db, review.repository, changesets, load_chunks=False)

    return assignChanges(
        db, user, review, changesets=changesets, update=True)

def queryFilters(db, user, review, globalfilters=False, parentfilters=False):
    with db.updating_cursor("reviews",
                            "reviewusers",
                            "reviewuserfiles",
                            # Updated indirectly via assignChanges().
                            "extensionfilterhookevents",
                            "extensionfilterhookcommits",
                            "extensionfilterhookfiles") as cursor:
        try:
            return _updateFilters(db, cursor, user, review, globalfilters, parentfilters)
        finally:
            db.rollback()

def applyFilters(db, user, review, globalfilters=False, parentfilters=False):
    with db.updating_cursor("reviews",
                            "reviewusers",
                            "reviewuserfiles",
                            "reviewmessageids",
                            # Updated indirectly via assignChanges().
                            "extensionfilterhookevents",
                            "extensionfilterhookcommits",
                            "extensionfilterhookfiles") as cursor:
        new_reviewers, new_watchers = _updateFilters(
            db, cursor, user, review, globalfilters, parentfilters)

        for user_id in new_reviewers:
            new_reviewer = dbutils.User.fromId(db, user_id)

            cursor.execute("""SELECT reviewfiles.file, SUM(reviewfiles.deleted), SUM(reviewfiles.inserted)
                                FROM reviewfiles
                                JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                               WHERE reviewfiles.review=%s
                                 AND reviewuserfiles.uid=%s
                            GROUP BY reviewfiles.file""",
                           (review.id, user_id))

            db.pending_mails.extend(mail.sendFiltersApplied(
                db, user, new_reviewer, review, globalfilters, parentfilters, cursor.fetchall()))

        for user_id in new_watchers:
            new_watcher = dbutils.User.fromId(db, user_id)
            db.pending_mails.extend(mail.sendFiltersApplied(
                db, user, new_watcher, review, globalfilters, parentfilters, None))

        review.incrementSerial(db)

def generateMailsForBatch(db, batch_id, was_accepted, is_accepted, profiler=None):
    cursor = db.readonly_cursor()
    cursor.execute("SELECT review, uid FROM batches WHERE id=%s", (batch_id,))

    review_id, user_id = cursor.fetchone()

    review = dbutils.Review.fromId(db, review_id)
    from_user = dbutils.User.fromId(db, user_id)

    recipients = review.getRecipients(db)
    for to_user in recipients:
        db.pending_mails.extend(mail.sendReviewBatch(db, from_user, to_user, recipients, review, batch_id, was_accepted, is_accepted, profiler=profiler))

def generateMailsForAssignmentsTransaction(db, transaction_id):
    cursor = db.readonly_cursor()
    cursor.execute("SELECT review, assigner, note FROM reviewassignmentstransactions WHERE id=%s", (transaction_id,))

    review_id, assigner_id, note = cursor.fetchone()

    review = dbutils.Review.fromId(db, review_id)
    assigner = dbutils.User.fromId(db, assigner_id)

    cursor.execute("""SELECT uid, path, type, created
                        FROM reviewfilterchanges
                       WHERE transaction=%s""",
                   (transaction_id,))

    by_user = {}

    for reviewer_id, path, filter_type, created in cursor:
        added_filters, removed_filters, unassigned, assigned = by_user.setdefault(reviewer_id, ([], [], [], []))
        if created: added_filters.append((filter_type, path or "/"))
        else: removed_filters.append((filter_type, path or "/"))

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

    for reviewer_id, (added_filters, removed_filters, unassigned, assigned) in by_user.items():
        reviewer = dbutils.User.fromId(db, reviewer_id)
        if assigner != reviewer:
            db.pending_mails.extend(mail.sendAssignmentsChanged(db, assigner, reviewer, review, added_filters, removed_filters, unassigned, assigned))

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
                            WHERE uid=%s
                              AND file IN (SELECT id
                                             FROM reviewfiles
                                            WHERE state='pending')""",
                   (user.id,))
