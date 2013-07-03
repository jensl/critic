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
import configuration
import textutils
import diff
from mailutils import queueMail, sendPendingMails, generateMessageId

import changeset.text as changeset_text
import changeset.utils as changeset_utils
import changeset.load as changeset_load
import log.commitset as log_commitset

import reviewing.comment as review_comment
import utils as review_utils

import time
import re
import os
import sys

def sendMail(db, review, message_id, from_user, to_user, recipients, subject, body, parent_message_id=None):
    return queueMail(from_user, to_user, recipients, subject, body,
                     review_url=review.getURL(db, to_user),
                     review_association=review.getUserAssociation(db, to_user),
                     review_repository=review.repository.getURL(db, to_user),
                     message_id=message_id,
                     parent_message_id=parent_message_id)

def generateSubjectLine(db, user, review, item):
    format = user.getPreference(db, "email.subjectLine.%s" % item)

    data = { "id": "r/%d" % review.id,
             "summary": review.summary,
             "progress": str(review.getReviewState(db)),
             "branch": review.branch.name }

    try: return format % data
    except Exception, exc: return "%s (format: %r)" % (str(exc), format)

def renderChainInMail(db, to_user, chain, focus_comment, new_state, new_type, line_length, context_lines):
    result = ""
    hr = "-" * line_length
    urls = to_user.getCriticURLs(db)
    url = "\n".join(["  %s/showcomment?chain=%d" % (url, chain.id) for url in urls])

    cursor = db.cursor()

    if chain.file_id:
        path = dbutils.describe_file(db, chain.file_id)

        if chain.first_commit == chain.last_commit or chain.origin == 'old':
            entry = chain.first_commit.getFileEntry(path)
        else:
            entry = chain.last_commit.getFileEntry(path)

        sha1 = entry.sha1
        mode = entry.mode

        first_line, count = chain.lines_by_sha1[sha1]

        context = changeset_utils.getCodeContext(db, sha1, first_line, minimized=True)
        if context: result += "%s in %s, %s:\n%s\n%s\n" % (chain.type.capitalize(), path, context, url, hr)
        else: result += "%s in %s:\n%s\n%s\n" % (chain.type.capitalize(), path, url, hr)

        file = diff.File(id=chain.file_id, path=path, new_mode=mode, new_sha1=sha1, repository=chain.review.repository)
        file.loadNewLines()
        lines = file.newLines(False)

        last_line = first_line + count - 1
        first_line = max(1, first_line - context_lines)
        last_line = min(last_line + context_lines, len(lines))
        width = len(str(last_line))

        for offset, line in enumerate(lines[first_line - 1:last_line]):
            result += "%s|%s\n" % (str(first_line + offset).rjust(width), line)

        result += hr + "\n"
    elif chain.first_commit:
        result += "%s in commit %s by %s:\n%s\n%s\n" % (chain.type.capitalize(), chain.first_commit.sha1[:8], chain.first_commit.author.name, url, hr)

        first_line, count = chain.lines_by_sha1[chain.first_commit.sha1]
        last_line = first_line + count - 1
        lines = chain.first_commit.message.splitlines()

        for line in lines[first_line:last_line + 1]:
            result += "  %s\n" % line

        result += hr + "\n"
    else:
        result += "General %s:\n%s\n%s\n" % (chain.type, url, hr)

    mode = to_user.getPreference(db, "email.updatedReview.quotedComments")

    def formatComment(comment):
        return "%s at %s:\n%s\n" % (comment.user.fullname, comment.when, textutils.reflow(comment.comment, line_length, indent=2))

    assert not focus_comment or focus_comment == chain.comments[-1], "focus comment (#%d) is not last in chain (#%d) as expected" % (focus_comment.id, chain.id)

    if not focus_comment or len(chain.comments) > 1:
        if focus_comment: comments = chain.comments[:-1]
        else: comments = chain.comments

        result = "\n".join(["> " + line for line in result.splitlines()]) + "\n"

        quote1 = ""
        notshown = ""
        quote2 = ""

        if mode == "first":
            quote1 = formatComment(comments[0])
            if len(comments) > 1:
                notshown = "[%d comment%s not shown]" % (len(comments) - 1, "s" if len(comments) > 2 else "")
        elif mode == "firstlast":
            quote1 = formatComment(comments[0])
            if len(comments) > 2:
                notshown = "[%d comment%s not shown]" % (len(comments) - 2, "s" if len(comments) > 3 else "")
            if len(comments) > 1:
                quote2 = formatComment(comments[-1])
        elif mode == "last":
            if len(comments) > 1:
                notshown = "[%d comment%s not shown]" % (len(comments) - 1, "s" if len(comments) > 2 else "")
            quote2 = formatComment(comments[-1])
        else:
            for comment in comments:
                quote1 += formatComment(comment)

        if quote1:
            result += "\n".join(["> " + line for line in quote1.splitlines()]) + "\n"
        if notshown:
            result += notshown + "\n"
        if quote2:
            result += "\n".join(["> " + line for line in quote2.splitlines()]) + "\n"

        if focus_comment:
            result += "\n"

    if focus_comment:
        result += formatComment(focus_comment)

    if new_type == "issue":
        result += "\nCONVERTED TO ISSUE!\n"
    elif new_type == "note":
        result += "\nCONVERTED TO NOTE!\n"

    if new_state == "closed":
        result += "\nISSUE RESOLVED!\n"
    elif new_state == "addressed":
        result += "\nISSUE ADDRESSED!\n"
    elif new_state == "open":
        result += "\nISSUE REOPENED!\n"
    elif chain.state == "closed":
        result += "\n(This issue is resolved.)\n"
    elif chain.state == "addressed":
        result += "\n(This issue is addressed.)\n"

    return result

def sendReviewCreated(db, from_user, to_user, recipients, review):
    # First check if the user has activated email sending at all.
    if not to_user.getPreference(db, "email.activated"): return []

    line_length = to_user.getPreference(db, "email.lineLength")
    hr = "-" * line_length

    data = { 'review.id': review.id,
             'review.url': review.getURL(db, to_user, 2),
             'review.owner.fullname': review.owners[0].fullname,
             'review.branch.name': review.branch.name,
             'review.branch.repository': review.repository.getURL(db, to_user),
             'hr': hr }

    body = """%(hr)s
This is an automatic message generated by the review at:
%(review.url)s
%(hr)s


""" % data

    body += """%(review.owner.fullname)s has requested a review of the changes on the branch
  %(review.branch.name)s
in the repository
  %(review.branch.repository)s


""" % data

    all_reviewers = to_user.getPreference(db, "email.newReview.displayReviewers")
    all_watchers = to_user.getPreference(db, "email.newReview.displayWatchers")

    if all_reviewers or all_watchers:
        if all_reviewers:
            if review.reviewers:
                body += "The users assigned to review the changes on the review branch are:\n"

                for reviewer in review.reviewers:
                    body += "  " + reviewer.fullname + "\n"

                body += "\n"
            else:
                body += """No reviewers have been identified for the changes in this review.  This means
the review is currently stuck; it cannot finish unless there are reviewers.

"""

        if all_watchers and review.watchers:
            body += "The following additional users are following the review:\n"

            for watcher in review.watchers:
                body += "  " + watcher.fullname + "\n"

            body += "\n"

        body += "\n"

    if review.description:
        body += """Description:
%s


""" % textutils.reflow(review.description, line_length, indent=2)

    cursor = db.cursor()
    cursor.execute("""SELECT file, SUM(deleted), SUM(inserted)
                        FROM fullreviewuserfiles
                       WHERE review=%s
                         AND assignee=%s
                    GROUP BY file""",
                   (review.id, to_user.id))
    pending_files_lines = cursor.fetchall()

    if pending_files_lines:
        body += renderFiles(db, to_user, review, "These changes were assigned to you:", pending_files_lines, showcommit_link=True)

    all_commits = to_user.getPreference(db, "email.newReview.displayCommits")

    if all_commits:
        body += "The commits requested to be reviewed are:\n\n"

        contextLines = to_user.getPreference(db, "email.newReview.diff.contextLines")
        diffMaxLines = to_user.getPreference(db, "email.newReview.diff.maxLines")

        displayStats = to_user.getPreference(db, "email.newReview.displayStats")
        statsMaxLines = to_user.getPreference(db, "email.newReview.stats.maxLines")

        if contextLines < 0: contextLines = 0

        commits = list(reversed(review.branch.commits))

        if diffMaxLines == 0: diffs = None
        else:
            diffs = {}
            lines = 0

            for commit in commits:
                if len(commit.parents) == 1:
                    cursor.execute("""SELECT id
                                        FROM reviewchangesets
                                        JOIN changesets ON (id=changeset)
                                       WHERE review=%s
                                         AND child=%s""", (review.id, commit.getId(db)))

                    (changeset_id,) = cursor.fetchone()

                    diff = changeset_text.unified(db, changeset_load.loadChangeset(db, review.repository, changeset_id), contextLines)
                    diffs[commit] = diff
                    lines += diff.count("\n")
                    if lines > diffMaxLines:
                        diffs = None
                        break

        if not displayStats or statsMaxLines == 0: stats = None
        else:
            stats = {}
            lines = 0

            for commit in commits:
                commit_stats = review.repository.run("show", "--oneline", "--stat", commit.sha1).split('\n', 1)[1]
                stats[commit] = commit_stats
                lines += commit_stats.count('\n')
                if lines > statsMaxLines:
                    stats = None
                    break

        for index, commit in enumerate(commits):
            if index > 0: body += "\n\n\n"

            body += """Commit: %(sha1)s
Author: %(author.fullname)s <%(author.email)s> at %(author.time)s

%(message)s
""" % { 'sha1': commit.sha1,
        'author.fullname': commit.author.getFullname(db),
        'author.email': commit.author.email,
        'author.time': time.strftime("%Y-%m-%d %H:%M:%S", commit.author.time),
        'message': textutils.reflow(commit.message.strip(), line_length, indent=2) }

            if stats and commit in stats:
                body += "---\n" + stats[commit]

            if diffs and commit in diffs:
                body += "\n" + diffs[commit]

    message_id = generateMessageId()

    cursor.execute("INSERT INTO reviewmessageids (uid, review, messageid) VALUES (%s, %s, %s)",
                   [to_user.id, review.id, message_id])

    return [sendMail(db, review, message_id, from_user, to_user, recipients, generateSubjectLine(db, to_user, review, 'newReview'), body)]

def renderFiles(db, to_user, review, title, files_lines, commits=None, relevant_only=False, relevant_files=None, showcommit_link=False):
    result = ""
    if files_lines:
        files = []

        for file_id, delete_count, insert_count in files_lines:
            if not relevant_only or file_id in relevant_files:
                files.append((dbutils.describe_file(db, file_id), delete_count, insert_count))

        if files:
            paths = []
            deleted = []
            inserted = []

            for path, delete_count, insert_count in sorted(files):
                paths.append(path)
                deleted.append(delete_count)
                inserted.append(insert_count)

            paths = diff.File.eliminateCommonPrefixes(paths, text=True)

            len_paths = max(map(len, paths))
            len_deleted = max(map(len, map(str, deleted)))
            len_inserted = max(map(len, map(str, inserted)))

            result += title + "\n"

            for path, delete_count, insert_count in zip(paths, deleted, inserted):
                if delete_count == 0 and insert_count == 0:
                    result += "  %s  binary file\n" % path.ljust(len_paths)
                else:
                    delete_field = delete_count > 0 and "-%d" % delete_count or ""
                    insert_field = insert_count > 0 and "+%d" % insert_count or ""
                    result += "  %s  %s %s\n" % (path.ljust(len_paths), delete_field.rjust(len_deleted + 1), insert_field.rjust(len_inserted + 1))

            if commits:
                if len(commits) == 1:
                    result += "from this commit:\n"
                else:
                    result += "from these commits:\n"

                for commit_id in commits:
                    commit = gitutils.Commit.fromId(db, review.repository, commit_id)
                    result += "  %s %s\n" % (commit.sha1[:8], commit.niceSummary())

            if showcommit_link:
                urls = to_user.getCriticURLs(db)

                try:
                    from_sha1, to_sha1 = showcommit_link
                    url_format = "  %%s/showcommit?review=%%d&from=%s&to=%s&filter=pending\n" % (from_sha1, to_sha1)
                except:
                    url_format = "  %s/showcommit?review=%d&filter=pending\n"

                result += "\nTo review all these changes:\n"
                for url in urls:
                    result += url_format % (url, review.id)

            result += "\n\n"
    return result

def sendReviewPlaceholder(db, to_user, review):
    # First check if the user has activated email sending at all.
    if not to_user.getPreference(db, "email.activated"): return []

    line_length = to_user.getPreference(db, "email.lineLength")
    hr = "-" * line_length

    why = "This message is sent to you when you become associated with a review after the review was initially requested.  It is then sent instead of the regular \"New Review\" message, for the purpose of using as the reference/in-reply-to message for other messages sent about this review."

    data = { 'review.id': review.id,
             'review.url': review.getURL(db, to_user, 2),
             'review.owner.fullname': review.owners[0].fullname,
             'review.branch.name': review.branch.name,
             'review.branch.repository': review.repository.getURL(db, to_user),
             'hr': hr,
             'why': textutils.reflow(why, line_length) }

    body = """%(hr)s
This is an automatic message generated by the review at:
%(review.url)s
%(hr)s


%(why)s


%(hr)s


""" % data

    body += """%(review.owner.fullname)s has requested a review of the changes on the branch
  %(review.branch.name)s
in the repository
  %(review.branch.repository)s


""" % data

    all_reviewers = to_user.getPreference(db, "email.newReview.displayReviewers")
    all_watchers = to_user.getPreference(db, "email.newReview.displayWatchers")

    if all_reviewers or all_watchers:
        if all_reviewers:
            if review.reviewers:
                body += "The users assigned to review the changes on the review branch are:\n"

                for reviewer in review.reviewers:
                    body += "  " + reviewer.fullname + "\n"

                body += "\n"
            else:
                body += """No reviewers have been identified for the changes in this review.  This means
the review is currently stuck; it cannot finish unless there are reviewers.

"""

        if all_watchers and review.watchers:
            body += "The following additional users are following the review:\n"

            for watcher in review.watchers:
                body += "  " + watcher.fullname + "\n"

            body += "\n"

        body += "\n"

    if review.description:
        body += """Description:
%s


""" % textutils.reflow(review.description, line_length, indent=2)

    message_id = generateMessageId()

    cursor = db.cursor()

    cursor.execute("INSERT INTO reviewmessageids (uid, review, messageid) VALUES (%s, %s, %s)",
                   [to_user.id, review.id, message_id])

    return [sendMail(db, review, message_id, review.owners[0], to_user, [to_user], generateSubjectLine(db, to_user, review, "newishReview"), body)]

def sendReviewBatch(db, from_user, to_user, recipients, review, batch_id, was_accepted, is_accepted, profiler=None):
    if profiler: profiler.check("generate mail: start")

    # First check if the user has activated email sending at all.
    if not to_user.getPreference(db, "email.activated"): return []
    if from_user == to_user and to_user.getPreference(db, "email.ignoreOwnChanges"): return []

    cursor = db.cursor()

    line_length = to_user.getPreference(db, "email.lineLength")
    relevant_only = to_user not in review.owners and to_user != from_user and to_user.getPreference(db, "email.updatedReview.relevantChangesOnly")
    mail_index = [0]

    if relevant_only:
        cursor.execute("SELECT type FROM reviewusers WHERE review=%s AND uid=%s", (review.id, to_user.id))
        if cursor.fetchone()[0] == 'manual': relevant_only = False

    def localGenerateMessageId():
        mail_index[0] += 1
        return generateMessageId(mail_index[0])

    if profiler: profiler.check("generate mail: prologue")

    if relevant_only:
        relevant_files = review.getRelevantFiles(db, to_user)
    else:
        relevant_files = None

    if profiler: profiler.check("generate mail: get relevant files")

    cursor.execute("SELECT comment FROM batches WHERE id=%s", [batch_id])
    batch_chain_id = cursor.fetchone()[0]

    if profiler: profiler.check("generate mail: batch chain")

    cursor.execute("""SELECT reviewfiles.file, SUM(reviewfiles.deleted), SUM(reviewfiles.inserted)
                        FROM reviewfiles
                        JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)
                       WHERE reviewfilechanges.batch=%s
                         AND reviewfilechanges.to='reviewed'
                    GROUP BY reviewfiles.file""",
                       (batch_id,))
    reviewed_files_lines = cursor.fetchall()

    if profiler: profiler.check("generate mail: reviewed files/lines")

    cursor.execute("""SELECT DISTINCT changesets.child
                        FROM reviewfiles
                        JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)
                        JOIN changesets ON (changesets.id=reviewfiles.changeset)
                       WHERE reviewfilechanges.batch=%s
                         AND reviewfilechanges.to='reviewed'""",
                       (batch_id,))
    reviewed_commits = cursor.fetchall()

    if profiler: profiler.check("generate mail: reviewed commits")

    cursor.execute("""SELECT reviewfiles.file, SUM(reviewfiles.deleted), SUM(reviewfiles.inserted)
                        FROM reviewfiles
                        JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)
                       WHERE reviewfilechanges.batch=%s
                         AND reviewfilechanges.to='pending'
                    GROUP BY reviewfiles.file""",
                   (batch_id,))
    unreviewed_files_lines = cursor.fetchall()

    if profiler: profiler.check("generate mail: unreviewed files/lines")

    cursor.execute("""SELECT DISTINCT changesets.child
                        FROM reviewfiles
                        JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)
                        JOIN changesets ON (changesets.id=reviewfiles.changeset)
                       WHERE reviewfilechanges.batch=%s
                         AND reviewfilechanges.to='pending'""",
                       (batch_id,))
    unreviewed_commits = cursor.fetchall()

    if profiler: profiler.check("generate mail: unreviewed commits")

    reviewed_files = renderFiles(db, to_user, review, "Reviewed Files:", reviewed_files_lines, reviewed_commits, relevant_only, relevant_files)
    unreviewed_files = renderFiles(db, to_user, review, "Unreviewed Files:", unreviewed_files_lines, unreviewed_commits, relevant_only, relevant_files)

    if profiler: profiler.check("generate mail: render files")

    context_lines = to_user.getPreference(db, "email.comment.contextLines")

    comment_ids = set()

    def isRelevantComment(chain):
        if chain.file_id is None or chain.file_id in relevant_files: return True

        cursor.execute("SELECT 1 FROM commentchainusers WHERE chain=%s AND uid=%s", (chain.id, to_user.id))
        return cursor.fetchone() is not None

    def fetchNewCommentChains():
        chains = []
        for (chain_id,) in cursor.fetchall():
            if chain_id != batch_chain_id:
                chain = review_comment.CommentChain.fromId(db, chain_id, from_user, review=review)
                if not relevant_only or isRelevantComment(chain):
                    chain.loadComments(db, from_user)
                    chains.append((chain, None, None))
        return chains

    def fetchAdditionalCommentChains():
        chains = []
        for chain_id, comment_id, new_state, new_type in cursor.fetchall():
            if comment_id is not None or new_state is not None or new_type is not None:
                chain = review_comment.CommentChain.fromId(db, chain_id, from_user, review=review)
                if not relevant_only or isRelevantComment(chain):
                    chain.loadComments(db, from_user)
                    chains.append((chain, new_state, new_type))
        return chains

    cursor.execute("SELECT id FROM commentchains WHERE batch=%s AND type='issue' ORDER BY id ASC", [batch_id])
    new_issues = fetchNewCommentChains()

    if profiler: profiler.check("generate mail: new issues")

    cursor.execute("SELECT id FROM commentchains WHERE batch=%s AND type='note' ORDER BY id ASC", [batch_id])
    new_notes = fetchNewCommentChains()

    if profiler: profiler.check("generate mail: new notes")

    cursor.execute("""SELECT commentchains.id, comments.id, commentchainchanges.to_state, commentchainchanges.to_type
                        FROM commentchains
             LEFT OUTER JOIN comments ON (commentchains.id=comments.chain
                                      AND comments.batch=%s)
             LEFT OUTER JOIN commentchainchanges ON (commentchains.id=commentchainchanges.chain
                                                 AND commentchainchanges.batch=%s)
                       WHERE commentchains.review=%s
                         AND commentchains.batch!=%s""",
                   [batch_id, batch_id, review.id, batch_id])
    additional_comments = fetchAdditionalCommentChains()

    if profiler: profiler.check("generate mail: additional comments")

    if is_accepted != was_accepted and not reviewed_files and not unreviewed_files and not new_issues and not new_notes and not additional_comments:
        return []

    data = { 'review.id': review.id,
             'review.url': review.getURL(db, to_user, 2),
             'review.branch.name': review.branch.name,
             'review.branch.repository': review.repository.getURL(db, to_user),
             'hr': "-" * line_length }

    header = """%(hr)s
This is an automatic message generated by the review at:
%(review.url)s
%(hr)s


""" % data

    if batch_chain_id is not None:
        batch_chain = review_comment.CommentChain.fromId(db, batch_chain_id, from_user, review=review)
    else:
        batch_chain = None

    data["batch.author.fullname"] = from_user.fullname

    first_name = from_user.getFirstName()

    if batch_chain is not None:
        batch_chain.loadComments(db, from_user)

        comment_ids.add(batch_chain.comments[0].id)

        remark = """%s'%s comment:
%s


""" % (first_name, first_name[-1] != 's' and 's' or '', textutils.reflow(batch_chain.comments[0].comment, line_length, indent=2))
    else:
        remark = ""

    body = header
    body += textutils.reflow("%(batch.author.fullname)s has submitted a batch of changes to the review." % data, line_length)
    body += "\n\n\n"
    body += remark

    if not was_accepted and is_accepted:
        state_change = textutils.reflow("The review is now ACCEPTED!", line_length) + "\n\n\n"
    elif was_accepted and not is_accepted:
        state_change = textutils.reflow("The review is NO LONGER ACCEPTED!", line_length) + "\n\n\n"
    else:
        state_change = ""

    body += state_change
    body += reviewed_files
    body += unreviewed_files

    subject = generateSubjectLine(db, to_user, review, "updatedReview.submittedChanges")

    def renderCommentChains(chains):
        result = ""
        if chains:
            for chain, new_state, new_type in chains:
                for focus_comment in chain.comments:
                    if focus_comment.batch_id == batch_id:
                        break
                else:
                    focus_comment = None
                if focus_comment is not None or new_state is not None or new_type is not None:
                    result += renderChainInMail(db, to_user, chain, focus_comment, new_state, new_type, line_length, context_lines) + "\n\n"
                if focus_comment is not None:
                    comment_ids.add(focus_comment.id)
        return result

    body += renderCommentChains(new_issues)
    body += renderCommentChains(new_notes)

    if profiler: profiler.check("generate mail: render new comment chains")

    comment_threading = to_user.getPreference(db, "email.updatedReview.commentThreading")

    send_main_mail = state_change or reviewed_files or unreviewed_files or new_issues or new_notes

    if not comment_threading:
        send_main_mail = send_main_mail or additional_comments
        body += renderCommentChains(additional_comments)

        if profiler: profiler.check("generate mail: render additional comments")

    review_message_id = [None]
    files = []

    def getReviewMessageId():
        if review_message_id[0] is None:
            cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [to_user.id, review.id])
            row = cursor.fetchone()

            if not row:
                files.extend(sendReviewPlaceholder(db, to_user, review))
                mail_index[0] += 1
                cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [to_user.id, review.id])
                row = cursor.fetchone()

            if row:
                review_message_id[0] = "<%s@%s>" % (row[0], configuration.base.HOSTNAME)

        return review_message_id[0]

    if send_main_mail:
        message_id = localGenerateMessageId()

        cursor.executemany("INSERT INTO commentmessageids (uid, comment, messageid) VALUES (%s, %s, %s)",
                           [(to_user.id, comment_id, message_id) for comment_id in comment_ids])

        files.append(sendMail(db, review, message_id, from_user, to_user, recipients, subject, body, parent_message_id=getReviewMessageId()))

    if comment_threading:
        threads = {}

        for chain, new_state, new_type in additional_comments:
            if chain.comments[-1].batch_id == batch_id:
                parent_comment_id = chain.comments[-2].id
            else:
                parent_comment_id = chain.comments[-1].id

            cursor.execute("""SELECT messageid
                                FROM commentmessageids
                               WHERE comment=%s
                                 AND uid=%s""",
                           [parent_comment_id, to_user.id])
            row = cursor.fetchone()

            if row: parent_message_id = "<%s@%s>" % (row[0], configuration.base.HOSTNAME)
            else: parent_message_id = getReviewMessageId()

            threads.setdefault(parent_message_id, []).append((chain, new_state, new_type))

        for parent_message_id, chains in threads.items():
            comment_ids = set()

            body = header + remark + renderCommentChains(chains)

            message_id = localGenerateMessageId()

            cursor.executemany("INSERT INTO commentmessageids (uid, comment, messageid) VALUES (%s, %s, %s)",
                               [(to_user.id, comment_id, message_id) for comment_id in comment_ids])

            files.append(sendMail(db, review, message_id, from_user, to_user, recipients, subject, body, parent_message_id=parent_message_id))

    if profiler: profiler.check("generate mail: finished")

    return files

def sendReviewAddedCommits(db, from_user, to_user, recipients, review, commits, changesets, tracked_branch=False):
    # First check if the user has activated email sending at all.
    if not to_user.getPreference(db, "email.activated"): return []
    if from_user == to_user and to_user.getPreference(db, "email.ignoreOwnChanges"): return []

    line_length = to_user.getPreference(db, "email.lineLength")
    hr = "-" * line_length
    relevant_only = to_user not in review.owners and to_user != from_user and to_user.getPreference(db, "email.updatedReview.relevantChangesOnly")

    cursor = db.cursor()

    if relevant_only:
        cursor.execute("SELECT type FROM reviewusers WHERE review=%s AND uid=%s", (review.id, to_user.id))
        if cursor.fetchone()[0] == 'manual': relevant_only = False

    all_commits = dict((commit.sha1, commit) for commit in commits)
    changeset_for_commit = {}

    for changeset in changesets:
        # We don't include diffs for merge commits in mails.
        if len(changeset.child.parents) == 1:
            if changeset.child in all_commits:
                changeset_for_commit[changeset.child] = changeset
            else:
                # An added changeset where the child isn't part of the added
                # commits will be a changeset between a "replayed rebase" commit
                # and the new head commit, generated when doing a non-fast-
                # forward rebase.  The relevant commit from such a changeset is
                # the first (and only) parent.
                changeset_for_commit[changeset.parent] = changeset

    if relevant_only:
        relevant_files = review.getRelevantFiles(db, to_user)
        relevant_commits = set()

        for changeset in changesets:
            for file in changeset.files:
                if file.id in relevant_files:
                    if changeset.child in all_commits:
                        relevant_commits.add(changeset.child)
                    else:
                        # "Replayed rebase" commit; see comment above.
                        relevant_commits.add(all_commits[changeset.parent])
                    break
            else:
                cursor.execute("SELECT id FROM commentchains WHERE review=%s AND state='addressed' AND addressed_by=%s", (review.id, changeset.child.getId(db)))
                for chain_id in cursor.fetchall():
                    cursor.execute("SELECT 1 FROM commentchainusers WHERE chain=%s AND uid=%s", (chain_id, to_user.id))
                    if cursor.fetchone():
                        relevant_commits.add(changeset.child)
                        break

        if not relevant_commits:
            return []
    else:
        relevant_commits = None

    data = { 'review.id': review.id,
             'review.url': review.getURL(db, to_user, 2),
             'review.branch.name': review.branch.name,
             'review.branch.repository': review.repository.getURL(db, to_user),
             'hr': hr }

    body = """%(hr)s
This is an automatic message generated by the review at:
%(review.url)s
%(hr)s


""" % data

    commitset = log_commitset.CommitSet(commits)

    if tracked_branch:
        body += "The automatic tracking of\n  %s\n" % tracked_branch
        body += textutils.reflow("has updated the review by pushing %sadditional commit%s to the branch" % ("an " if len(commits) == 1 else "", "s" if len(commits) > 1 else ""), line_length)
    else:
        body += textutils.reflow("%s has updated the review by pushing %sadditional commit%s to the branch" % (from_user.fullname, "an " if len(commits) == 1 else "", "s" if len(commits) > 1 else ""), line_length)

    body += "\n  %s\n" % review.branch.name
    body += textutils.reflow("in the repository", line_length)
    body += "\n  %s\n\n\n" % review.repository.getURL(db, to_user)

    cursor.execute("""SELECT file, SUM(deleted), SUM(inserted)
                        FROM fullreviewuserfiles
                       WHERE review=%%s
                         AND changeset IN (%s)
                         AND state='pending'
                         AND assignee=%%s
                    GROUP BY file""" % ",".join(["%s"] * len(changesets)),
                   [review.id] + [changeset.id for changeset in changesets] + [to_user.id])
    pending_files_lines = cursor.fetchall()

    if pending_files_lines:
        heads = commitset.getHeads()
        tails = commitset.getFilteredTails(review.repository)

        if len(heads) == 1 and len(tails) == 1:
            showcommit_link = (tails.pop()[:8], heads.pop().sha1[:8])
        else:
            showcommit_link = False

        body += renderFiles(db, to_user, review, "These changes were assigned to you:", pending_files_lines, showcommit_link=showcommit_link)

    all_commits = to_user.getPreference(db, "email.updatedReview.displayCommits")
    context_lines = to_user.getPreference(db, "email.comment.contextLines")

    if all_commits:
        body += "The additional commit%s requested to be reviewed are:\n\n" % ("s" if len(commits) > 1 else "")

        contextLines = to_user.getPreference(db, "email.updatedReview.diff.contextLines")
        diffMaxLines = to_user.getPreference(db, "email.updatedReview.diff.maxLines")

        displayStats = to_user.getPreference(db, "email.updatedReview.displayStats")
        statsMaxLines = to_user.getPreference(db, "email.updatedReview.stats.maxLines")

        if contextLines < 0: contextLines = 0

        if diffMaxLines == 0: diffs = None
        else:
            diffs = {}
            lines = 0

            for commit in commits:
                if commit in changeset_for_commit:
                    diff = changeset_text.unified(db, changeset_for_commit[commit], contextLines)
                    diffs[commit] = diff
                    lines += diff.count("\n")
                    if lines > diffMaxLines:
                        diffs = None
                        break

        if not displayStats or statsMaxLines == 0: stats = None
        else:
            stats = {}
            lines = 0

            for commit in commits:
                commit_stats = review.repository.run("show", "--oneline", "--stat", commit.sha1).split('\n', 1)[1]
                stats[commit] = commit_stats
                lines += commit_stats.count('\n')
                if lines > statsMaxLines:
                    stats = None
                    break

        for index, commit in enumerate(commits):
            if index > 0: body += "\n\n\n"

            body += """Commit: %(sha1)s
Author: %(author.fullname)s <%(author.email)s> at %(author.time)s

%(message)s
""" % { 'sha1': commit.sha1,
        'author.fullname': commit.author.getFullname(db),
        'author.email': commit.author.email,
        'author.time': time.strftime("%Y-%m-%d %H:%M:%S", commit.author.time),
        'message': textutils.reflow(commit.message.strip(), line_length, indent=2) }

            if stats and commit in stats:
                body += "---\n" + stats[commit]

            if diffs and commit in diffs:
                body += "\n" + diffs[commit]

            cursor.execute("SELECT id FROM commentchains WHERE review=%s AND state='addressed' AND addressed_by=%s", (review.id, commit.getId(db)))
            rows = cursor.fetchall()

            if rows:
                for (chain_id,) in rows:
                    chain = review_comment.CommentChain.fromId(db, chain_id, to_user, review=review)
                    chain.loadComments(db, to_user, include_draft_comments=False)
                    body += "\n\n" + renderChainInMail(db, to_user, chain, None, "addressed", None, line_length, context_lines)

    cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [to_user.id, review.id])
    row = cursor.fetchone()

    files = []

    if not row:
        files = sendReviewPlaceholder(db, to_user, review)
        cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [to_user.id, review.id])
        row = cursor.fetchone()

    if row: parent_message_id = "<%s@%s>" % (row[0], configuration.base.HOSTNAME)
    else: parent_message_id = None

    return files + [sendMail(db, review, generateMessageId(), from_user, to_user, recipients, generateSubjectLine(db, to_user, review, "updatedReview.commitsPushed"), body, parent_message_id=parent_message_id)]

def sendPing(db, from_user, to_user, recipients, review, note):
    # First check if the user has activated email sending at all.
    if not to_user.getPreference(db, "email.activated"): return []

    line_length = to_user.getPreference(db, "email.lineLength")
    hr = "-" * line_length

    data = { 'review.id': review.id,
             'review.url': review.getURL(db, to_user, 2),
             'review.branch.name': review.branch.name,
             'review.branch.repository': review.repository.getURL(db, to_user),
             'from.fullname': from_user.fullname,
             'hr': hr }

    body = """%(hr)s
This is an automatic message generated by the review at:
%(review.url)s
%(hr)s


""" % data

    body += """%(from.fullname)s has pinged the review!


""" % data

    if note:
        body += """Additional information from %s:
%s


""" % (from_user.getFirstName(), textutils.reflow(note, line_length, indent=2))

    cursor = db.cursor()

    cursor.execute("""SELECT reviewfiles.file, SUM(reviewfiles.deleted), SUM(reviewfiles.inserted)
                        FROM reviewfiles
                        JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                       WHERE reviewfiles.review=%s
                         AND reviewfiles.state='pending'
                         AND reviewuserfiles.uid=%s
                    GROUP BY reviewfiles.file""",
                   (review.id, to_user.id))
    pending_files_lines = cursor.fetchall()

    cursor.execute("""SELECT DISTINCT changesets.child
                        FROM reviewfiles
                        JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                        JOIN changesets ON (changesets.id=reviewfiles.changeset)
                       WHERE reviewfiles.review=%s
                         AND reviewfiles.state='pending'
                         AND reviewuserfiles.uid=%s""",
                   (review.id, to_user.id))
    pending_commits = cursor.fetchall()

    body += renderFiles(db, to_user, review, "These pending changes are assigned to you:", pending_files_lines, pending_commits, showcommit_link=True)

    cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [to_user.id, review.id])
    row = cursor.fetchone()

    if row: parent_message_id = "<%s@%s>" % (row[0], configuration.base.HOSTNAME)
    else: parent_message_id = None

    return [sendMail(db, review, generateMessageId(), from_user, to_user, recipients, generateSubjectLine(db, to_user, review, "pingedReview"), body, parent_message_id=parent_message_id)]

def sendAssignmentsChanged(db, from_user, to_user, review, added_filters, removed_filters, unassigned, assigned):
    # First check if the user has activated email sending at all.
    if not to_user.getPreference(db, "email.activated"): return []

    line_length = to_user.getPreference(db, "email.lineLength")
    hr = "-" * line_length

    data = { 'review.id': review.id,
             'review.url': review.getURL(db, to_user, 2),
             'review.branch.name': review.branch.name,
             'review.branch.repository': review.repository.getURL(db, to_user),
             'from.fullname': from_user.fullname,
             'hr': hr }

    body = """%(hr)s
This is an automatic message generated by the review at:
%(review.url)s
%(hr)s


""" % data

    body += """%(from.fullname)s has modified the assignments in the review.


""" % data

    def renderPaths(items):
        return "  \n".join(diff.File.eliminateCommonPrefixes(sorted(map(lambda item: item[1], items)), text=True)) + "\n"

    if added_filters or removed_filters:
        if added_filters:
            added_reviewer = filter(lambda item: item[0] == "reviewer", added_filters)
            added_watcher = filter(lambda item: item[0] == "watcher", added_filters)
        else:
            added_reviewer = None
            added_watcher = None

        if removed_filters:
            removed_reviewer = filter(lambda item: item[0] == "reviewer", removed_filters)
            removed_watcher = filter(lambda item: item[0] == "watcher", removed_filters)
        else:
            removed_reviewer = None
            removed_watcher = None

        if added_reviewer:
            body += "You are now reviewing the following paths:\n  %s\n" % renderPaths(added_reviewer)
        if added_watcher:
            body += "You are now watching the following paths:\n  %s\n" % renderPaths(added_watcher)
        if removed_reviewer:
            body += "You are no longer reviewing the following paths:\n  %s\n" % renderPaths(removed_reviewer)
        if removed_watcher:
            body += "You are no longer watching the following paths:\n  %s\n" % renderPaths(removed_watcher)

        body += "\n"

    if unassigned:
        body += renderFiles(db, to_user, review, "The following changes are no longer assigned to you:", unassigned)

    if assigned:
        body += renderFiles(db, to_user, review, "The following changes are now assigned to you:",assigned)

    files = []
    parent_message_id = None

    cursor = db.cursor()
    cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [to_user.id, review.id])
    row = cursor.fetchone()

    if not row:
        files.extend(sendReviewPlaceholder(db, to_user, review))
        cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [to_user.id, review.id])
        row = cursor.fetchone()

    if row:
        parent_message_id = "<%s@%s>" % (row[0], configuration.base.HOSTNAME)

    files.append(sendMail(db, review, generateMessageId(len(files) + 1), from_user, to_user, [to_user], generateSubjectLine(db, to_user, review, "updatedReview.assignmentsChanged"), body, parent_message_id=parent_message_id))

    return files

def sendFiltersApplied(db, from_user, to_user, review, globalfilters, parentfilters, assigned):
    # First check if the user has activated email sending at all.
    if not to_user.getPreference(db, "email.activated"): return []

    line_length = to_user.getPreference(db, "email.lineLength")
    hr = "-" * line_length

    data = { 'review.id': review.id,
             'review.url': review.getURL(db, to_user, 2),
             'review.branch.name': review.branch.name,
             'review.branch.repository': review.repository.getURL(db, to_user),
             'from.fullname': from_user.fullname,
             'hr': hr }

    body = """%(hr)s
This is an automatic message generated by the review at:
%(review.url)s
%(hr)s


""" % data

    if globalfilters:
        what = "global filters"
    else:
        what = "global filters from upstream repositories"

    text = ("%s has modified the assignments in the review by making %s apply, "
            "which they previously did not.  This had the effect that you are "
            "now a %s the review."
            % (from_user.fullname,
               what,
               "reviewer of changes in" if assigned else "watcher of"))

    body += """%s


""" % textutils.reflow(text, line_length)

    if assigned:
        body += renderFiles(db, to_user, review, "The following changes are now assigned to you:", assigned)

    files = []
    parent_message_id = None

    cursor = db.cursor()
    cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [to_user.id, review.id])
    row = cursor.fetchone()

    if not row:
        files.extend(sendReviewPlaceholder(db, to_user, review))
        cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [to_user.id, review.id])
        row = cursor.fetchone()

    if row:
        parent_message_id = "<%s@%s>" % (row[0], configuration.base.HOSTNAME)

    files.append(sendMail(db, review, generateMessageId(len(files) + 1), from_user, to_user, [to_user], generateSubjectLine(db, to_user, review, "updatedReview.parentFiltersApplied"), body, parent_message_id=parent_message_id))

    return files

def sendReviewRebased(db, from_user, to_user, recipients, review, new_upstream, rebased_commits, onto_branch=None):
    # First check if the user has activated email sending at all.
    if not to_user.getPreference(db, "email.activated"): return []
    if from_user == to_user and to_user.getPreference(db, "email.ignoreOwnChanges"): return []

    line_length = to_user.getPreference(db, "email.lineLength")
    hr = "-" * line_length

    data = { 'review.id': review.id,
             'review.url': review.getURL(db, to_user, 2),
             'review.branch.name': review.branch.name,
             'review.branch.repository': review.repository.getURL(db, to_user),
             'from.fullname': from_user.fullname,
             'hr': hr }

    body = """%(hr)s
This is an automatic message generated by the review at:
%(review.url)s
%(hr)s


""" % data

    if new_upstream or onto_branch:
        if onto_branch is None:
            data['target'] = "the commit '%s'" % new_upstream
        else:
            data['target'] = "the branch '%s'" % onto_branch

        text = "%(from.fullname)s has rebased the review branch onto %(target)s." % data
    else:
        text = "%(from.fullname)s has rewritten the history on the review branch." % data

    body += """%s


""" % textutils.reflow(text, line_length)

    body += """The new branch log is:

"""

    for commit in rebased_commits:
        body += "%s %s\n" % (commit.sha1[:8], commit.niceSummary())

    cursor = db.cursor()
    cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [to_user.id, review.id])
    row = cursor.fetchone()

    if row: parent_message_id = "<%s@%s>" % (row[0], configuration.base.HOSTNAME)
    else: parent_message_id = None

    return [sendMail(db, review, generateMessageId(), from_user, to_user, recipients, generateSubjectLine(db, to_user, review, "updatedReview.reviewRebased"), body, parent_message_id=parent_message_id)]

def sendExtensionOutput(db, user_id, batch_id, output):
    user = dbutils.User.fromId(db, user_id)

    # Explicitly *don't* check if the user has activated email sending.  This
    # allows a user to disable email sending and then install extensions whose
    # output is still sent.
    #if not user.getPreference(db, "email.activated"): return []

    line_length = user.getPreference(db, "email.lineLength")
    hr = "-" * line_length

    cursor = db.cursor()
    cursor.execute("SELECT review, uid FROM batches WHERE id=%s", (batch_id,))

    review_id, batch_user_id = cursor.fetchone()

    review = dbutils.Review.fromId(db, review_id)
    batch_user = dbutils.User.fromId(db, batch_user_id)

    data = { 'review.id': review.id,
             'review.url': review.getURL(db, user, 2),
             'batch.user.fullname': batch_user.fullname,
             'hr': hr }

    body = """%(hr)s
This is an automatic message generated by the review at:
%(review.url)s
%(hr)s


""" % data

    text = "A batch of changes submitted by %(batch.user.fullname)s has been processed by your installed extensions." % data

    body += """%s


""" % textutils.reflow(text, line_length)

    body += "The extensions generated the following output:\n%s" % output

    cursor.execute("SELECT messageid FROM reviewmessageids WHERE uid=%s AND review=%s", [user.id, review.id])
    row = cursor.fetchone()

    if row: parent_message_id = "<%s@%s>" % (row[0], configuration.base.HOSTNAME)
    else: parent_message_id = None

    return [sendMail(db, review, generateMessageId(), user, user, [user], generateSubjectLine(db, user, review, "extensionOutput"), body, parent_message_id=parent_message_id)]
