# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

import api
import apiobject
import dbutils

class Comment(apiobject.APIObject):
    wrapper_class = api.comment.Comment

    STATE_MAP = {
        # "Is draft" is a separate attribute, so use the state it would have
        # once published instead.
        "draft": "open",

        # "Closed" is only used in the database, really, the UI has always
        # called it "Resolve" (action) / "Resolved" (state).
        "closed": "resolved"
    }

    def __init__(self, chain_id, review_id, batch_id, author_id, comment_type,
                 state, side, timestamp, text, file_id, first_commit_id,
                 last_commit_id, addressed_by_id, resolved_by_id):
        self.id = chain_id
        self.is_draft = state == "draft"
        self.state = Comment.STATE_MAP.get(state, state)
        self.__review_id = review_id
        self.__batch_id = batch_id
        self.__author_id = author_id
        self.side = side
        self.timestamp = timestamp
        self.text = text
        self.__file_id = file_id
        self.__first_commit_id = first_commit_id
        self.__last_commit_id = last_commit_id
        self.__addressed_by_id = addressed_by_id
        self.__resolved_by_id = resolved_by_id

        if comment_type == "issue":
            self.wrapper_class = api.comment.Issue
        else:
            self.wrapper_class = api.comment.Note

    def getReview(self, critic):
        return api.review.fetch(critic, self.__review_id)

    def getAuthor(self, critic):
        return api.user.fetch(critic, self.__author_id)

    def getLocation(self, critic):
        cursor = critic.getDatabaseCursor()
        if self.__file_id is not None:
            repository = self.getReview(critic).repository
            if self.side == "old":
                commit = api.commit.fetch(repository, self.__first_commit_id)
            else:
                commit = api.commit.fetch(repository, self.__last_commit_id)
            file_sha1 = commit.getFileInformation(
                api.file.fetch(critic, file_id=self.__file_id)).sha1
            cursor.execute("""SELECT first_line, last_line
                                FROM commentchainlines
                               WHERE chain=%s
                                 AND sha1=%s""",
                           (self.id, file_sha1))
            first_line, last_line = cursor.fetchone()
            location = FileVersionLocation(
                self, first_line, last_line, repository, self.__file_id,
                first_commit_id=self.__first_commit_id,
                last_commit_id=self.__last_commit_id, side=self.side)
        elif self.__first_commit_id is not None:
            repository = self.getReview(critic).repository
            commit = api.commit.fetch(
                repository, commit_id=self.__first_commit_id)
            cursor.execute("""SELECT first_line, last_line
                                FROM commentchainlines
                               WHERE chain=%s
                                 AND sha1=%s""",
                           (self.id, commit.sha1))
            first_line, last_line = cursor.fetchone()
            # FIXME: Make commit message comment line numbers one-based too!
            first_line += 1
            last_line += 1
            # FIXME: ... and then delete the above two lines of code.
            location = CommitMessageLocation(
                first_line, last_line, repository, self.__first_commit_id)
        else:
            return None
        return location.wrap(critic)

    def getReplies(self, critic):
        return api.impl.reply.fetchForComment(critic, self.id)

    def getAddressedBy(self, critic):
        if self.state != "addressed":
            return None
        repository = self.getReview(critic).repository
        return api.commit.fetch(repository, commit_id=self.__addressed_by_id)

    def getResolvedBy(self, critic):
        if self.state != "resolved":
            return None
        return api.user.fetch(critic, user_id=self.__resolved_by_id)

    @staticmethod
    def refresh(critic, tables, cached_comments):
        if not tables.intersection(("commentchains", "comments")):
            return

        Comment.updateAll(
            critic,
            """SELECT commentchains.id, review, commentchains.batch,
                      commentchains.uid, type, commentchains.state,
                      origin, commentchains.time, comments.comment, file,
                      first_commit, last_commit, addressed_by, closed_by
                 FROM commentchains
                 JOIN comments ON (comments.id=first_comment)
                WHERE commentchains.id=ANY (%s)""",
            cached_comments)

@Comment.cached(api.comment.InvalidCommentId)
def fetch(critic, comment_id):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT commentchains.id, review, commentchains.batch,
                             commentchains.uid, type, commentchains.state,
                             origin, commentchains.time, comments.comment, file,
                             first_commit, last_commit, addressed_by, closed_by
                        FROM commentchains
                        JOIN comments ON (comments.id=first_comment)
                       WHERE commentchains.id=%s
                         AND commentchains.state!='empty'""",
                   (comment_id,))
    return Comment.make(critic, cursor)

@Comment.cachedMany(api.comment.InvalidCommentIds)
def fetchMany(critic, comment_ids):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT commentchains.id, review, commentchains.batch,
                             commentchains.uid, type, commentchains.state,
                             origin, commentchains.time, comments.comment, file,
                             first_commit, last_commit, addressed_by, closed_by
                        FROM commentchains
                        JOIN comments ON (comments.id=first_comment)
                       WHERE commentchains.id=ANY (%s)
                         AND commentchains.state!='empty'""",
                   (comment_ids,))
    return Comment.make(critic, cursor)

def fetchAll(critic, review, author, comment_type, state, location_type,
             changeset, commit):
    joins = ["JOIN comments ON (comments.id=first_comment)"]
    conditions = ["TRUE"]
    values = [critic.actual_user.id if critic.actual_user else None]
    if review:
        conditions.append("commentchains.review=%s")
        values.append(review.id)
    if author:
        conditions.append("commentchains.uid=%s")
        values.append(author.id)
    if comment_type:
        conditions.append("commentchains.type=%s")
        values.append(comment_type)
    if state:
        if state == "resolved":
            state = "closed"
        conditions.append("commentchains.state=%s")
        values.append(state)
    if location_type:
        if location_type == "commit-message":
            conditions.extend(["commentchains.file IS NULL",
                               "commentchains.first_commit IS NOT NULL"])
        else:
            conditions.extend(["commentchains.file IS NOT NULL"])
    if changeset is not None:
        joins.extend([
            "JOIN commentchainlines"
            " ON (commentchainlines.chain=commentchains.id)",
            "JOIN fileversions"
            " ON (fileversions.file=commentchains.file AND"
            "     commentchainlines.sha1 IN (fileversions.old_sha1,"
            "                                fileversions.new_sha1))"
        ])
        conditions.append("fileversions.changeset=%s")
        values.append(changeset.id)
    cursor = critic.getDatabaseCursor()
    cursor.execute(
        """SELECT DISTINCT commentchains.id, commentchains.review,
                           commentchains.batch, commentchains.uid,
                           commentchains.type, commentchains.state,
                           commentchains.origin, commentchains.time,
                           comments.comment, commentchains.file,
                           commentchains.first_commit,
                           commentchains.last_commit,
                           commentchains.addressed_by, commentchains.closed_by
             FROM commentchains
  LEFT OUTER JOIN batches ON (batches.comment=commentchains.id)
                  {}
            WHERE (commentchains.state!='draft' OR commentchains.uid=%s)
              AND commentchains.state!='empty'
              AND batches.id IS NULL
              AND {}
         ORDER BY commentchains.id""".format(
             " ".join(joins),
             " AND ".join(conditions)),
        values)
    comments = list(Comment.make(critic, cursor))
    if commit is not None:
        comments_by_id = { comment.id: comment for comment in comments }
        cursor.execute(
            """SELECT chain, sha1
                 FROM commentchainlines
                WHERE chain=ANY (%s)""",
            (comments_by_id.keys(),))
        comments_by_sha1 = dict()
        for comment_id, sha1 in cursor:
            comments_by_sha1.setdefault(sha1, set()).add(
                comments_by_id[comment_id])
        file_versions_cache = {}
        filtered_comments = []
        for comment in comments:
            if not comment.location:
                continue
            if comment.location.type == "commit-message":
                if comment.location.commit == commit:
                    filtered_comments.append(comment)
                continue
            file_id = comment.location.file.id
            if file_id not in file_versions_cache:
                try:
                    file_information = \
                        commit.getFileInformation(comment.location.file)
                except api.commit.NotAFile:
                    file_information = None
                file_versions_cache[file_id] = file_information
            else:
                file_information = file_versions_cache[file_id]
            if file_information is not None:
                if comment in comments_by_sha1.get(file_information.sha1, ()):
                    filtered_comments.append(comment)
        return filtered_comments
    return comments

class Location(apiobject.APIObject):
    def __init__(self, first_line, last_line):
        self.first_line = first_line
        self.last_line = last_line

class CommitMessageLocation(Location):
    wrapper_class = api.comment.CommitMessageLocation

    def __init__(self, first_line, last_line, repository, commit_id):
        super(CommitMessageLocation, self).__init__(first_line, last_line)
        self.repository = repository
        self.__commit_id = commit_id

    def getCommit(self, critic):
        return api.commit.fetch(self.repository, self.__commit_id)

def makeCommitMessageLocation(critic, first_line, last_line, commit):
    max_line = len(commit.message.splitlines())

    if last_line < first_line:
        raise api.comment.InvalidLocation(
            "first_line must be equal to or less than last_line")
    if last_line > max_line:
        raise api.comment.InvalidLocation(
            "last_line must be less than or equal to the number of lines in "
            "the commit message")

    return CommitMessageLocation(first_line, last_line, commit.repository,
                                 commit.id).wrap(critic)

class FileVersionLocation(Location):
    wrapper_class = api.comment.FileVersionLocation

    def __init__(self, comment, first_line, last_line, repository, file_id,
                 changeset=None, first_commit_id=None, last_commit_id=None,
                 side=None, commit=None, commit_id=None, is_translated=False):
        super(FileVersionLocation, self).__init__(first_line, last_line)
        self.comment = comment
        if first_commit_id is not None and first_commit_id == last_commit_id:
            commit_id = last_commit_id
            first_commit_id = last_commit_id = side = None
        self.repository = repository
        self.__file_id = file_id
        self.__changeset = changeset
        self.__first_commit_id = first_commit_id
        self.__last_commit_id = last_commit_id
        self.side = side
        self.__commit = commit
        self.__commit_id = commit_id
        self.is_translated = is_translated

    def getChangeset(self, critic):
        if self.__changeset:
            return self.__changeset
        if self.side is None:
            # Comment was made while looking at a single version of the file,
            # not while looking at a diff where the file was modified.
            return None
        from_commit = api.commit.fetch(
            self.repository, commit_id=self.__first_commit_id)
        to_commit = api.commit.fetch(
            self.repository, commit_id=self.__last_commit_id)
        return api.changeset.fetch(critic, self.repository,
                                   from_commit=from_commit, to_commit=to_commit)

    def getCommit(self, critic):
        if self.__commit:
            return self.__commit
        if self.__commit_id is None:
            return None
        return api.commit.fetch(self.repository, commit_id=self.__commit_id)

    def getFile(self, critic):
        return api.file.fetch(critic, file_id=self.__file_id)

    def translateTo(self, critic, changeset, commit):
        cursor = critic.getDatabaseCursor()

        def translateToCommit(target_commit, side):
            try:
                file_information = target_commit.getFileInformation(
                    self.getFile(critic))
            except api.commit.NotAFile:
                raise KeyError
            if not file_information:
                raise KeyError
            cursor.execute("""SELECT first_line, last_line
                                FROM commentchainlines
                               WHERE chain=%s
                                 AND sha1=%s""",
                           (self.comment.id, file_information.sha1,))
            row = cursor.fetchone()
            if row is None:
                raise KeyError
            first_line, last_line = row
            return FileVersionLocation(
                self.comment, first_line, last_line, self.repository,
                self.__file_id, changeset=changeset, side=side, commit=commit,
                is_translated=True).wrap(critic)

        if changeset:
            try:
                return translateToCommit(changeset.to_commit, "new")
            except KeyError:
                pass
            if changeset.from_commit:
                try:
                    return translateToCommit(changeset.from_commit, "old")
                except KeyError:
                    pass
        else:
            try:
                return translateToCommit(commit, None)
            except KeyError:
                pass

        return None

def makeFileVersionLocation(critic, first_line, last_line, file, changeset,
                            side, commit):
    if changeset is not None:
        repository = changeset.repository
        if side == "old":
            check_commit = changeset.from_commit
        else:
            check_commit = changeset.to_commit
    else:
        repository = commit.repository
        check_commit = commit

    max_line = len(check_commit.getFileLines(file))

    if last_line < first_line:
        raise api.comment.InvalidLocation(
            "first_line must be equal to or less than last_line")
    if last_line > max_line:
        raise api.comment.InvalidLocation(
            "last_line must be less than or equal to the number of lines in "
            "the file version")

    return FileVersionLocation(
        None, first_line, last_line, repository, file.id, changeset=changeset,
        side=side, commit=commit).wrap(critic)
