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
    def __init__(self, chain, batch_id, id, state, user, time, comment, code, unread):
        self.chain = chain
        self.batch_id = batch_id
        self.id = id
        self.state = state
        self.user = user
        self.time = time
        self.comment = comment
        self.code = code
        self.unread = unread

    def __repr__(self):
        return "Comment(%r)" % self.comment

    def when(self):
        return time.strftime("%Y-%m-%d %H:%M", self.time.timetuple())

    def getJSConstructor(self):
        return "new Comment(%d, %s, %s, %s, %s)" % (self.id, self.user.getJSConstructor(), jsify(strftime("%Y-%m-%d %H:%M", self.time.timetuple())), jsify(self.state), jsify(self.comment))

    @staticmethod
    def fromId(db, id, user):
        cursor = db.cursor()
        cursor.execute("SELECT chain, batch, uid, time, state, comment, code FROM comments WHERE id=%s", (id,))
        row = cursor.fetchone()
        if not row: return None
        else:
            chain_id, batch_id, user_id, time, state, comment, code = row
            cursor.execute("SELECT 1 FROM commentstoread WHERE uid=%s AND comment=%s", (user.id, id))
            return Comment(CommentChain.fromId(db, chain_id, user), batch_id, id, state,  dbutils.User.fromId(db, user_id), time, comment, code, cursor.fetchone() is not None)

class CommentChain:
    def __init__(self, id, user, review, batch_id, type, state, origin=None, file_id=None, first_commit=None, last_commit=None, closed_by=None, addressed_by=None, type_is_draft=False, state_is_draft=False, leader=None, count=None, unread=None):
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

        self.closed_by = closed_by
        self.addressed_by = addressed_by

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
        draft_user_id = user.id if include_draft_comments else None

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
        for comment_id, batch_id, comment_state, user_id, time, comment, code, unread in cursor.fetchall():
            comment = Comment(self, batch_id, comment_id, comment_state, dbutils.User.fromId(db, user_id), time, comment, code, unread)
            if comment_state == 'draft': last = comment
            else: self.comments.append(comment)
        if last: self.comments.append(last)

    def when(self):
        return time.strftime("%Y-%m-%d %H:%M", self.comments[0].time.timetuple())

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

            cursor.execute("""SELECT from_type, to_type, from_state, to_state, from_last_commit, to_last_commit
                                FROM commentchainchanges
                               WHERE chain=%s
                                 AND uid=%s
                                 AND state='draft'""",
                           [id, user.id])

            for from_type, to_type, from_state, to_state, from_last_commit_id, to_last_commit_id in cursor:
                if from_state == state and from_last_commit_id == last_commit_id:
                    state = to_state
                    state_is_draft = True
                    last_commit_id = to_last_commit_id
                    if to_state != "open":
                        closed_by_id = user.id
                if from_type == type:
                    type = to_type
                    type_is_draft = True

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

            chain = CommentChain(id, dbutils.User.fromId(db, user_id), review, batch_id, type, state, origin, file_id, first_commit, last_commit, closed_by, addressed_by, type_is_draft=type_is_draft, state_is_draft=state_is_draft)

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
    elif file is not None and changeset is None:
        cursor.execute("""SELECT DISTINCT id
                          FROM commentchains
                            LEFT OUTER JOIN commentchainlines ON (id=chain)
                          WHERE review=%s AND file=%s AND count(sha1)=0
                          GROUP BY id, review, commentchains.uid, type, commentchains.state, file""",
                       [review.id, file.id])
    elif commit is not None:
        cursor.execute("""SELECT DISTINCT id
                          FROM commentchains
                            JOIN commentchainlines ON (id=chain)
                          WHERE review=%s
                            AND file IS NULL
                            AND commit=%s
                            AND ((commentchains.state!='draft' OR commentchains.uid=%s)
                                 AND commentchains.state!='empty')
                          GROUP BY id""",
                       [review.id, commit.getId(db), user.id])
    elif local_comments_only:
        cursor.execute("""SELECT DISTINCT id
                          FROM commentchains
                            INNER JOIN commentchainlines ON (id=chain)
                            INNER JOIN fileversions ON (commentchains.file=fileversions.file)
                          WHERE review=%s
                            AND commentchains.file=%s
                            AND commentchains.state!='empty'
                            AND ((commentchains.first_commit=%s AND commentchains.last_commit=%s)
                              OR commentchains.addressed_by=%s)
                            AND fileversions.changeset=%s
                            AND (sha1=fileversions.old_sha1 OR sha1=fileversions.new_sha1)
                            AND (commentchainlines.state='current' OR commentchainlines.uid=%s)
                            ORDER BY id ASC""",
                       [review.id, file.id, changeset.parent.getId(db), changeset.child.getId(db), changeset.child.getId(db), changeset.id, user.id])
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
    if chain_type == "issue" and review.state != "open":
        raise OperationFailure(code="reviewclosed",
                               title="Review is closed!",
                               message="You need to reopen the review before you can raise new issues.")

    cursor = db.cursor()

    if file_id is not None and (parent_id == child_id or parent_id is None):
        cursor.execute("""SELECT 1
                            FROM reviewchangesets
                            JOIN fileversions USING (changeset)
                           WHERE reviewchangesets.review=%s
                             AND fileversions.file=%s
                             AND fileversions.old_sha1!='0000000000000000000000000000000000000000'
                             AND fileversions.new_sha1!='0000000000000000000000000000000000000000'""",
                       (review.id, file_id))

        if cursor.fetchone():
            cursor.execute("""SELECT parent, child
                                FROM changesets
                                JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                                JOIN fileversions ON (fileversions.changeset=changesets.id)
                               WHERE fileversions.file=%s
                                 AND fileversions.new_sha1=%s""",
                           (file_id, new_sha1))

            rows = cursor.fetchall()

            if not rows:
                cursor.execute("""SELECT parent, child
                                    FROM changesets
                                    JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                                    JOIN fileversions ON (fileversions.changeset=changesets.id)
                                   WHERE fileversions.file=%s
                                     AND fileversions.old_sha1=%s""",
                               (file_id, new_sha1))

                rows = cursor.fetchall()

            parent = child = None

            for row_parent_id, row_child_id in rows:
                if row_child_id == child_id:
                    parent = gitutils.Commit.fromId(db, review.repository, row_parent_id)
                    child = gitutils.Commit.fromId(db, review.repository, row_child_id)
                    break
                elif row_parent_id == child_id and parent is None:
                    parent = gitutils.Commit.fromId(db, review.repository, row_parent_id)
                    child = gitutils.Commit.fromId(db, review.repository, row_child_id)

            if parent and child:
                url = "/%s/%s..%s?review=%d&file=%d" % (review.repository.name, parent.sha1[:8], child.sha1[:8], review.id, file_id)
                link = ("<p>The link below goes to a diff that can be use to create the comment:</p>" +
                        "<p style='padding-left: 2em'><a href='%s'>%s%s</a></p>") % (url, dbutils.getURLPrefix(db), url)
            else:
                link = ""

            raise OperationFailure(code="notsupported",
                                   title="File changed in review",
                                   message=("<p>Due to limitations in the code used to create comments, " +
                                            "it's only possible to create comments via a diff view if " +
                                            "the commented file has been changed in the review.</p>" +
                                            link),
                                   is_html=True)

        cursor.execute("""INSERT INTO commentchains (review, uid, type, file, first_commit, last_commit)
                               VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id""",
                       (review.id, user.id, chain_type, file_id, child_id, child_id))
        chain_id = cursor.fetchone()[0]

        cursor.execute("""INSERT INTO commentchainlines (chain, uid, commit, sha1, first_line, last_line)
                               VALUES (%s, %s, %s, %s, %s, %s)""",
                       (chain_id, user.id, child_id, new_sha1, offset, offset + count - 1))
    elif file_id is not None:
        parents_returned = set()

        def getFileParent(new_sha1):
            cursor.execute("""SELECT changesets.id, fileversions.old_sha1
                                FROM changesets, reviewchangesets, fileversions
                               WHERE reviewchangesets.review=%s
                                 AND reviewchangesets.changeset=changesets.id
                                 AND fileversions.changeset=changesets.id
                                 AND fileversions.file=%s
                                 AND fileversions.new_sha1=%s""",
                           [review.id, file_id, new_sha1])
            try:
                changeset_id, old_sha1 = cursor.fetchone()
                if old_sha1 in parents_returned: return None, None
                parents_returned.add(old_sha1)
                return changeset_id, old_sha1
            except:
                return None, None

        children_returned = set()

        def getFileChild(old_sha1):
            cursor.execute("""SELECT changesets.id, fileversions.new_sha1
                                FROM changesets, reviewchangesets, fileversions
                               WHERE reviewchangesets.review=%s
                                 AND reviewchangesets.changeset=changesets.id
                                 AND fileversions.changeset=changesets.id
                                 AND fileversions.file=%s
                                 AND fileversions.old_sha1=%s""",
                           [review.id, file_id, old_sha1])
            try:
                changeset_id, new_sha1 = cursor.fetchone()
                if new_sha1 in children_returned: return None, None
                children_returned.add(new_sha1)
                return changeset_id, new_sha1
            except:
                return None, None

        cursor.execute("""SELECT changesets.id
                            FROM changesets, reviewchangesets, fileversions
                           WHERE reviewchangesets.review=%s
                             AND reviewchangesets.changeset=changesets.id
                             AND changesets.child=%s
                             AND fileversions.changeset=changesets.id
                             AND fileversions.file=%s
                             AND fileversions.old_sha1=%s
                             AND fileversions.new_sha1=%s""",
                       [review.id, child_id, file_id, old_sha1, new_sha1])

        row = cursor.fetchone()

        if not row:
            if origin == "old":
                cursor.execute("""SELECT changesets.id
                                    FROM changesets, reviewchangesets, fileversions
                                   WHERE reviewchangesets.review=%s
                                     AND reviewchangesets.changeset=changesets.id
                                     AND fileversions.changeset=changesets.id
                                     AND fileversions.file=%s
                                     AND fileversions.old_sha1=%s""",
                               [review.id, file_id, old_sha1])
            else:
                cursor.execute("""SELECT changesets.id
                                    FROM changesets, reviewchangesets, fileversions
                                   WHERE reviewchangesets.review=%s
                                     AND reviewchangesets.changeset=changesets.id
                                     AND fileversions.changeset=changesets.id
                                     AND fileversions.file=%s
                                     AND fileversions.new_sha1=%s""",
                               [review.id, file_id, new_sha1])

            row = cursor.fetchone()

        primary_changeset_id = row[0]

        sha1s_older = { }
        sha1s_newer = { old_sha1: (primary_changeset_id, new_sha1) }

        sha1 = new_sha1
        while True:
            changeset_id, next_sha1 = getFileParent(sha1)
            if changeset_id:
                sha1s_older[sha1] = changeset_id, next_sha1
                sha1s_newer[next_sha1] = changeset_id, sha1
                sha1 = next_sha1
            else:
                break

        sha1 = new_sha1
        while True:
            changeset_id, next_sha1 = getFileChild(sha1)
            if changeset_id:
                sha1s_newer[sha1] = changeset_id, next_sha1
                sha1 = next_sha1
            else:
                break

        commentchainlines_values = []
        processed = set()

        def searchOrigin(changeset_id, sha1, search_space, first_line, last_line):
            try:
                while sha1 not in processed:
                    processed.add(sha1)
                    changeset_id, next_sha1 = search_space[sha1]
                    changeset = changeset_load.loadChangeset(db, review.repository, changeset_id, filtered_file_ids=set([file_id]))
                    if len(changeset.child.parents) > 1: break
                    verdict, next_first_line, next_last_line = updateCommentChain(first_line, last_line, changeset.files[0].chunks, forward)
                    if verdict == "modified": break
                    sha1 = next_sha1
                    first_line = next_first_line
                    last_line = next_last_line
            except:
                pass
            return changeset_id, sha1, first_line, last_line

        first_line = offset
        last_line = offset + count - 1

        if origin == 'old':
            changeset_id, sha1, first_line, last_line = searchOrigin(primary_changeset_id, old_sha1, sha1s_older, first_line, last_line)
            commit_id = diff.Changeset.fromId(db, review.repository, changeset_id).parent.id
        else:
            changeset_id, sha1, first_line, last_line = searchOrigin(primary_changeset_id, new_sha1, sha1s_older, first_line, last_line)
            commit_id = diff.Changeset.fromId(db, review.repository, changeset_id).child.id

        commentchainlines_values.append((user.id, commit_id, sha1, first_line, last_line))
        processed = set()
        processed.add(sha1)

        while sha1 in sha1s_newer:
            changeset_id, sha1 = sha1s_newer[sha1]

            if sha1 in processed: break
            else: processed.add(sha1)

            changeset = changeset_load.loadChangeset(db, review.repository, changeset_id, filtered_file_ids=set([file_id]))

            if len(changeset.child.parents) != 1:
                chunks = diff.parse.parseDifferences(review.repository, from_commit=changeset.parent, to_commit=changeset.child, selected_path=dbutils.describe_file(db, file_id)).chunks
            else:
                chunks = changeset.files[0].chunks

            verdict, first_line, last_line = updateCommentChain(first_line, last_line, chunks)

            if verdict == "transfer":
                commentchainlines_values.append((user.id, changeset.child.getId(db), sha1, first_line, last_line))
            else:
                break

        cursor.execute("INSERT INTO commentchains (review, uid, type, origin, file, first_commit, last_commit) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id", [review.id, user.id, chain_type, origin, file_id, parent_id, child_id])
        chain_id = cursor.fetchone()[0]

        try: cursor.executemany("INSERT INTO commentchainlines (chain, uid, commit, sha1, first_line, last_line) VALUES (%s, %s, %s, %s, %s, %s)", [(chain_id,) + values for values in commentchainlines_values])
        except: raise Exception, repr(commentchainlines_values)
    elif commit_id is not None:
        commit = gitutils.Commit.fromId(db, review.repository, commit_id)

        cursor.execute("INSERT INTO commentchains (review, uid, type, first_commit, last_commit) VALUES (%s, %s, %s, %s, %s) RETURNING id", [review.id, user.id, chain_type, commit_id, commit_id])
        chain_id = cursor.fetchone()[0]

        cursor.execute("INSERT INTO commentchainlines (chain, uid, commit, sha1, first_line, last_line) VALUES (%s, %s, %s, %s, %s, %s)", (chain_id, user.id, commit_id, commit.sha1, offset, offset + count - 1))
    else:
        cursor.execute("INSERT INTO commentchains (review, uid, type) VALUES (%s, %s, %s) RETURNING id", [review.id, user.id, chain_type])
        chain_id = cursor.fetchone()[0]

    commentchainusers = set([user.id] + map(int, review.owners))

    if file_id is not None:
        filters = Filters()
        filters.load(db, review=review)

        for user_id in filters.listUsers(db, file_id):
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

def updateCommentChain(first_line, last_line, chunks, forward=True):
    delta = 0

    for chunk in chunks:
        if forward:
            if chunk.delete_offset + chunk.delete_count <= first_line:
                # Chunk is before (and does not overlap) the comment chain.
                delta += chunk.insert_count - chunk.delete_count
            elif chunk.delete_offset <= last_line:
                # Chunk overlaps the comment chain.
                return ("modified", None, None)
            else:
                # Chunk is after comment chain, which thus was not overlapped by
                # any chunk.  Copy the comment chain over to the new version of
                # the file with 'delta' added to its 'first_line'/'last_line'.
                return ("transfer", first_line + delta, last_line + delta)
        else:
            if chunk.insert_offset + chunk.insert_count <= first_line:
                # Chunk is before (and does not overlap) the comment chain.
                delta += chunk.delete_count - chunk.insert_count
            elif chunk.insert_offset <= last_line:
                # Chunk overlaps the comment chain.
                return ("modified", None, None)
            else:
                # Chunk is after comment chain, which thus was not overlapped by
                # any chunk.  Copy the comment chain over to the new version of
                # the file with 'delta' added to its 'first_line'/'last_line'.
                return ("transfer", first_line + delta, last_line + delta)
    else:
        # Comment chain was after all the chunks.  Copy it over to the new
        # version of the file with 'delta' added to its 'first_line' and
        # 'last_line'.
        return ("transfer", first_line + delta, last_line + delta)

def updateCommentChains(db, user, review, changeset):
    cursor = db.cursor()

    commentchainlines_values = []
    addressed = set()

    for file in changeset.files:
        cursor.execute("""SELECT id, commentchains.uid, type, commentchains.state, first_line, last_line
                          FROM commentchains
                            INNER JOIN commentchainlines ON (id=chain)
                          WHERE commentchains.review=%s
                            AND commentchains.state in ('draft', 'open')
                            AND commentchains.file=%s
                            AND commentchainlines.sha1=%s
                       ORDER BY commentchainlines.first_line""",
                       [review.id, file.id, file.old_sha1])

        rows = cursor.fetchall()
        if not rows: continue

        if len(changeset.child.parents) != 1:
            full_file = diff.parse.parseDifferences(review.repository, from_commit=changeset.parent, to_commit=changeset.child, selected_path=file.path)
            if not full_file: continue
            chunks = full_file.chunks
        else:
            chunks = file.chunks

        for chain_id, chain_user_id, chain_type, chain_state, first_line, last_line in rows:
            verdict, new_first_line, new_last_line = updateCommentChain(first_line, last_line, chunks)

            if verdict == "modified" and chain_type == "issue": addressed.add(chain_id)
            elif verdict == "transfer":
                cursor.execute("SELECT 1 FROM commentchainlines WHERE chain=%s AND sha1=%s", (chain_id, file.new_sha1))
                if not cursor.fetchone():
                    if chain_state == 'open':
                        lines_state = 'current'
                        lines_user_id = user.id
                    else:
                        lines_state = 'draft'
                        lines_user_id = chain_user_id

                    commentchainlines_values.append([chain_id, lines_user_id, lines_state, changeset.child.getId(db), file.new_sha1, new_first_line, new_last_line])

    cursor.executemany("""INSERT INTO commentchainlines (chain, uid, state, commit, sha1, first_line, last_line)
                          VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                       commentchainlines_values)

    if addressed:
        cursor.executemany("UPDATE commentchains SET state='addressed', addressed_by=%s WHERE id=%s AND state='open'", [[changeset.child.id, chain_id] for chain_id in addressed])
        cursor.executemany("UPDATE commentchains SET addressed_by=%s WHERE id=%s AND state='draft'", [[changeset.child.id, chain_id] for chain_id in addressed])

        print "Addressed issues:"
        for chain_id in addressed:
            chain = CommentChain.fromId(db, chain_id, user, review=review)
            if chain.state == 'addressed':
                chain.loadComments(db, user)
                title = "  %s: " % chain.title(False)
                print "%s%s" % (title, chain.leader(max_length=80 - len(title), text=True))

def validateCommentChain(db, review, file_id, sha1, offset, count):
    """Check whether the commented lines are changed by later commits in the review.
If they are, a diff.Changeset object representing the first changeset that
modifies those lines is returned.  If they are not, None is returned."""

    cursor = db.cursor()
    cursor.execute("""SELECT old_sha1, new_sha1, reviewchangesets.changeset
                      FROM reviewchangesets, fileversions
                      WHERE reviewchangesets.review=%s
                        AND fileversions.changeset=reviewchangesets.changeset
                        AND fileversions.file=%s""",
                   [review.id, file_id])

    sha1s = {}

    for old_sha1, new_sha1, changeset_id in cursor.fetchall():
        sha1s[old_sha1] = (new_sha1, changeset_id)

    commit_count = 0
    processed = set()

    while sha1 in sha1s and sha1 not in processed:
        processed.add(sha1)

        commit_count += 1
        sha1, changeset_id = sha1s[sha1]

        cursor.execute("""SELECT deleteOffset, deleteCount, insertOffset, insertCount
                          FROM chunks
                          WHERE changeset=%s
                            AND file=%s
                          ORDER BY deleteOffset ASC""",
                       [changeset_id, file_id])

        for delete_offset, delete_count, insert_offset, insert_count in cursor.fetchall():
            if insert_offset + delete_count <= offset:
                offset += insert_count - delete_count
            elif offset + count <= insert_offset:
                break
            else:
                return "modified", { "sha1": diff.Changeset.fromId(db, review.repository, changeset_id).child.sha1,
                                     "offset": offset }

    if commit_count > 0: return "transferred", { "count": commit_count }
    else: return "clean", {}
