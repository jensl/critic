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
import diff
import diff.parse
import time
import gitutils
import itertools
import changeset.load as changeset_load
import htmlutils
import re
import page.utils

from htmlutils import jsify
from time import strftime
from reviewing.filters import Filters
from operation import OperationFailure

class Comment:
    def __init__(self, chain, batch_id, id, state, user, time, when, comment, code, unread):
        self.chain = chain
        self.batch_id = batch_id
        self.id = id
        self.state = state
        self.user = user
        self.time = time
        self.when = when
        self.comment = comment
        self.code = code
        self.unread = unread

    def __repr__(self):
        return "Comment(%r)" % self.comment

    def getJSConstructor(self):
        return "new Comment(%d, %s, %s, %s, %s)" % (self.id, self.user.getJSConstructor(), jsify(strftime("%Y-%m-%d %H:%M", self.time.timetuple())), jsify(self.state), jsify(self.comment))

    @staticmethod
    def fromId(db, id, user):
        cursor = db.cursor()
        cursor.execute("SELECT chain, batch, uid, time, state, comment, code FROM comments WHERE id=%s", (id,))
        row = cursor.fetchone()
        if not row: return None
        else:
            chain_id, batch_id, author_id, time, state, comment, code = row
            author = dbutils.User.fromId(db, author_id)
            adjusted_time = user.adjustTimestamp(db, time)
            when = user.formatTimestamp(db, time)
            cursor.execute("SELECT 1 FROM commentstoread WHERE uid=%s AND comment=%s", (user.id, id))
            return Comment(CommentChain.fromId(db, chain_id, user), batch_id, id, state, author, adjusted_time, when, comment, code, cursor.fetchone() is not None)

class CommentChain:
    def __init__(self, id, user, review, batch_id, type, state, origin=None, file_id=None, first_commit=None, last_commit=None, closed_by=None, addressed_by=None, type_is_draft=False, state_is_draft=False, last_commit_is_draft=False, addressed_by_is_draft=False, leader=None, count=None, unread=None):
        self.id = id
        self.user = user
        self.review = review
        self.batch_id = batch_id
        self.type = type
        self.type_is_draft = type_is_draft
        self.state = state
        self.state_is_draft = state_is_draft
        self.origin = origin
        self.file_id = file_id
        self.first_commit = first_commit
        self.last_commit = last_commit
        self.last_commit_is_draft = last_commit_is_draft

        self.closed_by = closed_by
        self.addressed_by = addressed_by
        self.addressed_by_is_draft = addressed_by_is_draft

        self.lines = None
        self.lines_by_sha1 = None

        self.__leader = leader
        self.__count = count
        self.__unread = unread
        self.comments = []

    def setLines(self, sha1, offset, count):
        if not self.lines:
            self.lines = []
            self.lines_by_sha1 = {}
        assert sha1 not in self.lines
        self.lines.append((sha1, offset, count))
        self.lines_by_sha1[sha1] = (offset, count)
        return self

    def loadComments(self, db, user, include_draft_comments=True):
        if include_draft_comments:
            if self.state == "draft":
                draft_user_id = self.user.id
            else:
                draft_user_id = user.id
        else:
            draft_user_id = None

        cursor = db.cursor()
        cursor.execute("""SELECT comments.id,
                                 comments.batch,
                                 comments.state,
                                 comments.uid,
                                 comments.time,
                                 comments.comment,
                                 comments.code,
                                 commentstoread.uid IS NOT NULL AS unread
                            FROM comments
                 LEFT OUTER JOIN commentstoread ON (comments.id=commentstoread.comment AND commentstoread.uid=%s)
                           WHERE comments.chain=%s
                             AND ((comments.state='draft' AND comments.uid=%s) OR comments.state='current')
                        ORDER BY time""",
                       (user.id, self.id, draft_user_id))
        last = None
        for comment_id, batch_id, comment_state, author_id, time, comment, code, unread in cursor.fetchall():
            author = dbutils.User.fromId(db, author_id)
            adjusted_time = user.adjustTimestamp(db, time)
            when = user.formatTimestamp(db, time)
            comment = Comment(self, batch_id, comment_id, comment_state, author,
                              adjusted_time, when, comment, code, unread)
            if comment_state == 'draft': last = comment
            else: self.comments.append(comment)
        if last: self.comments.append(last)

    def when(self):
        return self.comments[0].when

    def countComments(self):
        if self.__count is None:
            self.__count = len(self.comments)
        return self.__count

    def countUnread(self):
        if self.__unread is None:
            self.__unread = len(filter(lambda comment: comment.unread, self.comments))
        return self.__unread

    def title(self, include_time=True):
        if self.type == "issue":
            result = "Issue raised by %s" % (self.user.fullname)
        else:
            result = "Note by %s" % (self.user.fullname)
        if include_time:
            result += " at %s" % self.when()
        return result

    def leader(self, max_length=80, text=False):
        if self.__leader is None: self.__leader = self.comments[0].comment.split("\n", 1)[0]
        if len(self.__leader) > max_length:
            if text: return self.__leader[:max_length - 5] + "[...]"
            else: return htmlutils.htmlify(self.__leader[:max_length - 3]) + "[&#8230;]"
        else:
            if text: return self.__leader
            else: return htmlutils.htmlify(self.__leader)

    def getJSConstructor(self, sha1=None):
        if self.closed_by: closed_by = self.closed_by.getJSConstructor()
        else: closed_by = "null"

        if self.addressed_by: addressed_by = jsify(self.addressed_by.sha1)
        else: addressed_by = "null"

        comments = ", ".join(map(Comment.getJSConstructor, self.comments))

        if sha1:
            offset, count = self.lines_by_sha1[sha1]
            if self.file_id:
                lines = "new CommentLines(%d, %s, %d, %d)" % (self.file_id, jsify(sha1), offset, offset + count - 1)
            else:
                lines = "new CommentLines(null, %s, %d, %d)" % (jsify(sha1), offset, offset + count - 1)
        else:
            lines = "null"

        return "new CommentChain(%d, %s, %s, %s, %s, %s, %s, [%s], %s)" % (self.id, self.user.getJSConstructor(), jsify(self.type), "true" if self.type_is_draft else "false", jsify(self.state), closed_by, addressed_by, comments, lines)

    def __nonzero__(self):
        return bool(self.comments)

    def __eq__(self, other):
        return other is not None and self.id == other.id

    def __ne__(self, other):
        return other is None or self.id != other.id

    def __repr__(self):
        return "CommentChain(%d)" % self.id

    def __len__(self):
        return len(self.comments)

    def __getitem__(self, index):
        return self.comments[index]

    @staticmethod
    def fromReview(db, review, user):
        cursor = db.cursor()
        cursor.execute("""SELECT commentchains.id, commentchains.batch,
                                 users.id, users.name, users.email, users.fullname, users.status,
                                 commentchains.type, drafttype.to_type,
                                 commentchains.state, draftstate.to_state,
                                 SUBSTRING(comments.comment FROM 1 FOR 81),
                                 chaincomments(commentchains.id),
                                 chainunread(commentchains.id, %s)
                            FROM commentchains
                            JOIN users ON (users.id=commentchains.uid)
                            JOIN comments ON (comments.id=commentchains.first_comment)
                 LEFT OUTER JOIN commentchainchanges AS drafttype ON (drafttype.chain=commentchains.id
                                                                  AND drafttype.uid=%s
                                                                  AND drafttype.to_type IS NOT NULL
                                                                  AND drafttype.state='draft')
                 LEFT OUTER JOIN commentchainchanges AS draftstate ON (draftstate.chain=commentchains.id
                                                                   AND draftstate.uid=%s
                                                                   AND draftstate.to_state IS NOT NULL
                                                                   AND draftstate.state='draft')
                           WHERE commentchains.review=%s
                             AND (commentchains.state!='draft' or commentchains.uid=%s)
                        ORDER BY commentchains.id ASC""",
                       (user.id, user.id, user.id, review.id, user.id,))
        chains = []
        for chain_id, batch_id, user_id, user_name, user_email, user_fullname, user_status, chain_type, draft_type, chain_state, draft_state, leader, count, unread in cursor:
            if draft_type is not None: chain_type = draft_type
            if draft_state is not None: chain_state = draft_state

            if "\n" in leader: leader = leader[:leader.index("\n")]

            chains.append(CommentChain(chain_id, dbutils.User(user_id, user_name, user_email, user_fullname, user_status), review, batch_id, chain_type, chain_state, leader=leader, count=count, unread=unread))

        return chains

    @staticmethod
    def fromId(db, id, user, review=None, skip=None):
        cursor = db.cursor()
        cursor.execute("SELECT review, batch, uid, type, state, origin, file, first_commit, last_commit, closed_by, addressed_by FROM commentchains WHERE id=%s", [id])
        row = cursor.fetchone()
        if not row: return None
        else:
            review_id, batch_id, user_id, type, state, origin, file_id, first_commit_id, last_commit_id, closed_by_id, addressed_by_id = row
            type_is_draft = False
            state_is_draft = False
            last_commit_is_draft = False
            addressed_by_is_draft = False

            cursor.execute("""SELECT from_type, to_type,
                                     from_state, to_state,
                                     from_last_commit, to_last_commit,
                                     from_addressed_by, to_addressed_by
                                FROM commentchainchanges
                               WHERE chain=%s
                                 AND uid=%s
                                 AND state='draft'""",
                           [id, user.id])

            for from_type, to_type, from_state, to_state, from_last_commit_id, to_last_commit_id, from_addressed_by_id, to_addressed_by_id in cursor:
                if from_state == state:
                    state = to_state
                    state_is_draft = True
                    if to_state != "open":
                        closed_by_id = user.id
                if from_type == type:
                    type = to_type
                    type_is_draft = True
                if from_last_commit_id == last_commit_id:
                    last_commit_id = from_last_commit_id
                    last_commit_is_draft = True
                if from_addressed_by_id == addressed_by_id:
                    addressed_by_id = to_addressed_by_id
                    addressed_by_is_draft = True

            if review is None:
                review = dbutils.Review.fromId(db, review_id, load_commits=False)
            else:
                assert review.id == review_id

            first_commit = last_commit = addressed_by = None

            if not skip or 'commits' not in skip:
                if first_commit_id: first_commit = gitutils.Commit.fromId(db, review.repository, first_commit_id)
                if last_commit_id: last_commit = gitutils.Commit.fromId(db, review.repository, last_commit_id)
                if addressed_by_id: addressed_by = gitutils.Commit.fromId(db, review.repository, addressed_by_id)

            if closed_by_id: closed_by = dbutils.User.fromId(db, closed_by_id)
            else: closed_by = None

            chain = CommentChain(id, dbutils.User.fromId(db, user_id), review,
                                 batch_id, type, state, origin, file_id,
                                 first_commit, last_commit, closed_by, addressed_by,
                                 type_is_draft=type_is_draft,
                                 state_is_draft=state_is_draft,
                                 last_commit_is_draft=last_commit_is_draft,
                                 addressed_by_is_draft=addressed_by_is_draft)

            if not skip or 'lines' not in skip:
                cursor.execute("SELECT sha1, first_line, last_line FROM commentchainlines WHERE chain=%s AND (state='current' OR uid=%s)", (id, user.id))
                for sha1, first_line, last_line in cursor.fetchall():
                    chain.setLines(sha1, first_line, last_line - first_line + 1)

            return chain

def loadCommentChains(db, review, user, file=None, changeset=None, commit=None, local_comments_only=False):
    result = []
    cursor = db.cursor()

    chain_ids = None

    if file is None and changeset is None and commit is None:
        cursor.execute("SELECT id FROM commentchains WHERE review=%s AND file IS NULL", [review.id])
    elif commit is not None:
        cursor.execute("""SELECT DISTINCT id
                            FROM commentchains
                           WHERE review=%s
                             AND file IS NULL
                             AND first_commit=%s
                             AND ((state!='draft' OR uid=%s)
                               AND state!='empty')
                        GROUP BY id""",
                       [review.id, commit.getId(db), user.id])
    elif local_comments_only:
        cursor.execute("""SELECT DISTINCT commentchains.id
                            FROM commentchains
                            JOIN commentchainlines ON (commentchainlines.chain=commentchains.id)
                            JOIN fileversions ON (fileversions.file=commentchains.file)
                           WHERE commentchains.review=%s
                             AND commentchains.file=%s
                             AND commentchains.state!='empty'
                             AND ((commentchains.first_commit=%s AND commentchains.last_commit=%s)
                               OR commentchains.addressed_by=%s)
                             AND fileversions.changeset=%s
                             AND (commentchainlines.sha1=fileversions.old_sha1
                               OR commentchainlines.sha1=fileversions.new_sha1)
                             AND (commentchainlines.state='current'
                               OR commentchainlines.uid=%s)
                        ORDER BY commentchains.id ASC""",
                       (review.id, file.id, changeset.parent.getId(db), changeset.child.getId(db), changeset.child.getId(db), changeset.id, user.id))
    else:
        chain_ids = set()

        if file is not None: files = [file]
        else: files = changeset.files

        for file in files:
            cursor.execute("""SELECT id
                                FROM commentchains
                                JOIN commentchainlines ON (commentchainlines.chain=commentchains.id)
                               WHERE commentchains.review=%s
                                 AND commentchains.file=%s
                                 AND commentchains.state!='empty'
                                 AND (commentchains.state!='draft' OR commentchains.uid=%s)
                                 AND (commentchainlines.sha1=%s
                                   OR commentchainlines.sha1=%s)
                                 AND (commentchainlines.state='current'
                                   OR commentchainlines.uid=%s)""",
                           (review.id, file.id, user.id, file.old_sha1, file.new_sha1, user.id))

            for (chain_id,) in cursor.fetchall():
                chain_ids.add(chain_id)

    if chain_ids is None:
        chain_ids = set()

        for (chain_id,) in cursor.fetchall():
            chain_ids.add(chain_id)

    for chain_id in sorted(chain_ids):
        chain = CommentChain.fromId(db, chain_id, user, review=review)
        chain.loadComments(db, user)
        result.append(chain)

    return result

def createCommentChain(db, user, review, chain_type, commit_id=None, origin=None, file_id=None, parent_id=None, child_id=None, old_sha1=None, new_sha1=None, offset=None, count=None):
    import reviewing.comment.propagate

    if chain_type == "issue" and review.state != "open":
        raise OperationFailure(code="reviewclosed",
                               title="Review is closed!",
                               message="You need to reopen the review before you can raise new issues.")

    cursor = db.cursor()

    if file_id is not None:
        if origin == "old":
            commit = gitutils.Commit.fromId(db, review.repository, parent_id)
        else:
            commit = gitutils.Commit.fromId(db, review.repository, child_id)

        propagation = reviewing.comment.propagate.Propagation(db)

        if not propagation.setCustom(review, commit, file_id, offset, offset + count - 1):
            raise OperationFailure(code="invalidoperation",
                                   title="Invalid operation",
                                   message="It's not possible to create a comment here.")

        propagation.calculateInitialLines()

        cursor.execute("""INSERT INTO commentchains (review, uid, type, origin, file, first_commit, last_commit)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING id""",
                       (review.id, user.id, chain_type, origin, file_id, parent_id, child_id))

        chain_id = cursor.fetchone()[0]
        commentchainlines_values = []

        for sha1, (first_line, last_line) in propagation.new_lines.items():
            commentchainlines_values.append((chain_id, user.id, sha1, first_line, last_line))

        cursor.executemany("""INSERT INTO commentchainlines (chain, uid, sha1, first_line, last_line)
                                   VALUES (%s, %s, %s, %s, %s)""",
                           commentchainlines_values)
    elif commit_id is not None:
        commit = gitutils.Commit.fromId(db, review.repository, commit_id)

        cursor.execute("""INSERT INTO commentchains (review, uid, type, first_commit, last_commit)
                               VALUES (%s, %s, %s, %s, %s)
                            RETURNING id""",
                       (review.id, user.id, chain_type, commit_id, commit_id))
        chain_id = cursor.fetchone()[0]

        cursor.execute("""INSERT INTO commentchainlines (chain, uid, sha1, first_line, last_line)
                               VALUES (%s, %s, %s, %s, %s)""",
                       (chain_id, user.id, commit.sha1, offset, offset + count - 1))
    else:
        cursor.execute("""INSERT INTO commentchains (review, uid, type)
                               VALUES (%s, %s, %s)
                            RETURNING id""",
                       (review.id, user.id, chain_type))
        chain_id = cursor.fetchone()[0]

    commentchainusers = set([user.id] + map(int, review.owners))

    if file_id is not None:
        filters = Filters()
        filters.setFiles(db, review=review)
        filters.load(db, review=review)

        for user_id in filters.listUsers(file_id):
            commentchainusers.add(user_id)

    cursor.executemany("INSERT INTO commentchainusers (chain, uid) VALUES (%s, %s)", [(chain_id, user_id) for user_id in commentchainusers])

    return chain_id

def createComment(db, user, chain_id, comment, first=False):
    cursor = db.cursor()

    cursor.execute("INSERT INTO comments (chain, uid, time, state, comment) VALUES (%s, %s, now(), 'draft', %s) RETURNING id", (chain_id, user.id, comment))
    comment_id = cursor.fetchone()[0]

    if first:
        cursor.execute("UPDATE commentchains SET first_comment=%s WHERE id=%s", (comment_id, chain_id))

    return comment_id

def validateCommentChain(db, review, origin, parent_id, child_id, file_id, offset, count):
    """
    Check whether the commented lines are changed by later commits in the
    review.

    If they are, a diff.Changeset object representing the first changeset that
    modifies those lines is returned.  If they are not, None is returned.
    """

    import reviewing.comment.propagate

    if origin == "old":
        commit = gitutils.Commit.fromId(db, review.repository, parent_id)
    else:
        commit = gitutils.Commit.fromId(db, review.repository, child_id)

    propagation = reviewing.comment.propagate.Propagation(db)

    if not propagation.setCustom(review, commit, file_id, offset, offset + count - 1):
        return "invalid", {}

    propagation.calculateInitialLines()

    if propagation.active:
        file_path = dbutils.describe_file(db, file_id)

        if commit.getFileSHA1(file_path) != review.branch.head.getFileSHA1(file_path):
            return "transferred", {}
        else:
            return "clean", {}
    else:
        addressed_by = propagation.addressed_by[0]

        return "modified", { "parent_sha1": addressed_by.parent.sha1,
                             "child_sha1": addressed_by.child.sha1,
                             "offset": addressed_by.location.first_line }

def propagateCommentChains(db, user, review, commits):
    import reviewing.comment.propagate

    cursor = db.cursor()
    cursor.execute("""SELECT id, uid, type, state, file
                        FROM commentchains
                       WHERE review=%s
                         AND file IS NOT NULL""",
                   (review.id,))

    chains_by_file = {}

    for chain_id, chain_user_id, chain_type, chain_state, file_id in cursor:
        chains_by_file.setdefault(file_id, {})[chain_id] = (chain_user_id, chain_type, chain_state)

    commentchainlines_values = []
    addressed_values = []

    for file_id, chains in chains_by_file.items():
        file_path = dbutils.describe_file(db, file_id)
        file_sha1 = review.branch.head.getFileSHA1(file_path)

        cursor.execute("""SELECT chain, first_line, last_line
                            FROM commentchainlines
                           WHERE chain=ANY (%s)
                             AND sha1=%s""",
                       (chains.keys(), file_sha1))

        for chain_id, first_line, last_line in cursor:
            propagation = reviewing.comment.propagate.Propagation(db)
            propagation.setExisting(review, chain_id, review.branch.head, file_id, first_line, last_line)
            propagation.calculateAdditionalLines(commits)

            chain_user_id, chain_type, chain_state = chains[chain_id]
            lines_state = "draft" if chain_state == "draft" else "current"

            for sha1, (first_line, last_line) in propagation.new_lines.items():
                commentchainlines_values.append((chain_id, chain_user_id, lines_state, sha1, first_line, last_line))

            if chain_type == "issue" and chain_state in ("open", "draft") and not propagation.active:
                addressed_values.append((propagation.addressed_by[0].child.getId(db), chain_id))

    cursor.executemany("""INSERT INTO commentchainlines (chain, uid, state, sha1, first_line, last_line)
                          VALUES (%s, %s, %s, %s, %s, %s)""",
                       commentchainlines_values)

    if addressed_values:
        cursor.executemany("UPDATE commentchains SET state='addressed', addressed_by=%s WHERE id=%s AND state='open'", addressed_values)
        cursor.executemany("UPDATE commentchains SET addressed_by=%s WHERE id=%s AND state='draft'", addressed_values)

        print "Addressed issues:"
        for commit_id, chain_id in addressed_values:
            chain = CommentChain.fromId(db, chain_id, user, review=review)
            if chain.state == 'addressed':
                chain.loadComments(db, user)
                title = "  %s: " % chain.title(False)
                print "%s%s" % (title, chain.leader(max_length=80 - len(title), text=True))
