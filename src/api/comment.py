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

class CommentError(api.APIError):
    pass

class InvalidCommentId(CommentError):
    """Raised when an invalid comment id is used."""

    def __init__(self, comment_id):
        """Constructor"""
        super(InvalidCommentId, self).__init__(
            "Invalid comment id: %d" % comment_id)
        self.comment_id = comment_id

class InvalidCommentIds(CommentError):
    """Raised by fetchMany() when invalid comment ids are used."""

    def __init__(self, comment_ids):
        """Constructor"""
        super(InvalidCommentIds, self).__init__(
            "Invalid comment ids: %s" % ", ".join(map(str, comment_ids)))
        self.comment_ids = comment_ids

class InvalidLocation(CommentError):
    """Raised when attempting to specify an invalid comment location"""

    pass

class Comment(api.APIObject):
    TYPE_VALUES = frozenset(["issue", "note"])

    @property
    def id(self):
        """The comment's unique id"""
        return self._impl.id

    @property
    def type(self):
        """The comment's type

           The type is one of "issue" and "note"."""
        pass

    @property
    def is_draft(self):
        """True if the comment is not yet published

           Unpublished comments are not displayed to other users."""
        return self._impl.is_draft

    @property
    def review(self):

        """The review to which the comment belongs

           The review is returned as an api.review.Review object."""
        return self._impl.getReview(self.critic)

    @property
    def author(self):
        """The comment's author

           The author is returned as an api.user.User object."""
        return self._impl.getAuthor(self.critic)

    @property
    def timestamp(self):
        """The comment's timestamp

           The return value is a datetime.datetime object."""
        return self._impl.timestamp

    @property
    def location(self):
        """The location of the comment, or None

           If the comment was made against lines in a commit message, the return
           value is a api.comment.CommitMessageLocation object.  If the comment
           was made against lines in a file version, the return value is
           api.comment.FileVersionLocation object.  Otherwise, the return value
           is None."""
        return self._impl.getLocation(self.critic)

    @property
    def text(self):
        """The comment's text"""
        return self._impl.text

    @property
    def replies(self):
        """The replies to the comment

           The replies are returned as a list of api.reply.Reply objects."""
        return self._impl.getReplies(self.critic)

    class DraftChanges(object):
        """Draft changes to the comment"""

        def __init__(self, author, is_draft, reply, new_type):
            self.__author = author
            self.__is_draft = is_draft
            self.__reply = reply
            self.__new_type = new_type

        @property
        def author(self):
            """The author of these draft changes

               The author is returned as an api.user.User object."""
            return self.__author

        @property
        def is_draft(self):
            """True if the comment itself is a draft (not published)"""
            return self.__is_draft

        @property
        def reply(self):
            """The current unpublished reply

               The reply is returned as an api.reply.Reply object, or None if
               there is no current unpublished reply."""
            return self.__reply

        @property
        def new_type(self):
            """The new type of an unpublished type change

               The type is returned as a string. Comment.TYPE_VALUES defines the
               set of possible return values."""
            return self.__new_type

    @property
    def draft_changes(self):
        """The comment's current draft changes

           The draft changes are returned as a Comment.DraftChanges object, or
           None if the current user has no unpublished changes to this comment.

           If the comment is currently an issue, or the current user has an
           unpublished change of the comment's type to issue, the returned
           object will be an Issue.DraftChanges instead."""
        return self._impl.getDraftChanges(self.critic)

class Issue(Comment):
    STATE_VALUES = frozenset(["open", "addressed", "resolved"])

    @property
    def type(self):
        return "issue"

    @property
    def state(self):
        """The issue's state

           The state is one of the strings "open", "addressed" or "resolved"."""
        return self._impl.state

    @property
    def addressed_by(self):
        """The commit that addressed the issue, or None

           The value is an api.commit.Commit object, or None if the issue's
           state is not "addressed"."""
        return self._impl.getAddressedBy(self.critic)

    @property
    def resolved_by(self):
        """The user that resolved the issue, or None

           The value is an api.user.User object, or None if the issue's state is
           not "resolved"."""
        return self._impl.getResolvedBy(self.critic)

    class DraftChanges(Comment.DraftChanges):
        """Draft changes to the issue"""

        def __init__(self, author, is_draft, reply, new_type, new_state,
                     new_location):
            super(Issue.DraftChanges, self).__init__(
                author, is_draft, reply, new_type)
            self.__new_state = new_state
            self.__new_location = new_location

        @property
        def new_state(self):
            """The issue's new state

               The new state is returned as a string, or None if the current
               user has not resolved or reopened the issue. Issue.STATE_VALUES
               defines the set of possible return values."""
            return self.__new_state

        @property
        def new_location(self):
            """The issue's new location

               The new location is returned as a FileVersionLocation objects, or
               None if the issue has not been reopened, or if it was manually
               resolved rather than addressed and did not need to be relocated
               when being reopened.

               Since only issues in file version locations can be addressed,
               that is the only possible type of new location."""
            return self.__new_location

class Note(Comment):
    @property
    def type(self):
        return "note"

class Location(api.APIObject):
    TYPE_VALUES = frozenset(["general", "commit-message", "file-version"])

    def __len__(self):
        """Return the the length of the location, in lines"""
        return (self.last_line - self.first_line) + 1

    @property
    def type(self):
        """The location's type

           The type is one of "commit-message" and "file-version"."""
        pass

    @property
    def first_line(self):
        """The line number of the first commented line

           Note that line numbers are one-based."""
        return self._impl.first_line

    @property
    def last_line(self):
        """The line number of the last commented line

           Note that line numbers are one-based."""
        return self._impl.last_line

class CommitMessageLocation(Location):
    @property
    def type(self):
        return "commit-message"

    @property
    def commit(self):
        """The commit whose message was commented"""
        return self._impl.getCommit(self.critic)

    @staticmethod
    def make(critic, first_line, last_line, commit):
        return api.impl.comment.makeCommitMessageLocation(
            critic, first_line, last_line, commit)

class FileVersionLocation(Location):
    @property
    def type(self):
        return "file-version"

    @property
    def changeset(self):
        """The changeset containing the comment

           The changeset is returned as an api.changeset.Changeset object.

           If the comment was created while looking at a diff, this will
           initially be that changeset. As additional commits are added to the
           review, this changeset may be "extended" to contain those added
           commits.

           This is the ideal changeset to use to display the comment, unless it
           is an issue that has been addressed, in which case a better changeset
           would be the diff of the commit returned by Issue.addressed_by.

           If the user did not make the comment while looking at a diff but
           rather while looking at a single version of the file, then this
           attribute returns None.

           If this is an object returned by translateTo() called with a
           changeset argument, then this will be that changeset."""
        return self._impl.getChangeset(self.critic)

    @property
    def side(self):
        """The commented side ("old" or "new") of the changeset

           If the user did not make the comment while looking at a changeset
           (i.e. a diff) but rather while looking at a single version of the
           file, then this attribute returns None."""
        return self._impl.side

    @property
    def commit(self):
        """The commit whose version of the file this location references

           The commit is returned as an api.commit.Commit object.

           If this is an object returned by translateTo() called with a commit
           argument, then this is the commit that was given as an argument to
           it. If this is the primary location of the comment (returned from
           Comment.location) then this is the commit whose version of the file
           the comment was originally made against, or None if the comment was
           made while looking at a diff."""
        return self._impl.getCommit(self.critic)

    @property
    def file(self):
        """The commented file"""
        return self._impl.getFile(self.critic)

    @property
    def is_translated(self):
        """True if this is a location returned by |translateTo()|"""
        return self._impl.is_translated

    def translateTo(self, changeset=None, commit=None):
        """Return a translated file version location, or None

           The location is translated to the version of the file in a certain
           commit. If |changeset| is not None, that commit is the changeset's
           |to_commit|, unless the comment is not present there, and otherwise
           the changeset's |from_commit|. If |commit| is not None, that's the
           commit.

           If the comment is not present in the commit, None is returned.

           The returned object's |is_translated| will be True.

           If the |changeset| argument is not None, then the returned object's
           |changeset| will be that changeset, and its |side| will reflect which
           of its |from_commit| and |to_commit| ended up being used. The
           returned object's |commit| will be None.

           If the |commit| argument is not None, the returned object's |commit|
           will be that commit, and its |changeset| and |side| will be None."""
        assert changeset is None \
                or isinstance(changeset, api.changeset.Changeset)
        assert commit is None or isinstance(commit, api.commit.Commit)
        assert (changeset is None) != (commit is None)
        return self._impl.translateTo(self.critic, changeset, commit)

    @staticmethod
    def make(critic, first_line, last_line, file, changeset=None, side=None,
             commit=None):
        # File is required.
        assert isinstance(file, api.file.File)
        # Changeset and side go together.
        assert (changeset is None) == (side is None)
        assert (changeset is None) \
                or isinstance(changeset, api.changeset.Changeset)
        # Commit conflicts with changeset, but one is required.
        assert (commit is None) != (changeset is None)
        assert (commit is None) or isinstance(commit, api.commit.Commit)
        return api.impl.comment.makeFileVersionLocation(
            critic, first_line, last_line, file, changeset, side, commit)

def fetch(critic, comment_id):
    """Fetch the Comment object with the given id"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(comment_id, int)
    return api.impl.comment.fetch(critic, comment_id)

def fetchMany(critic, comment_ids):
    """Fetch multiple Comment objects with the given ids"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    comment_ids = list(comment_ids)
    assert all(isinstance(comment_id, int) for comment_id in comment_ids)
    return api.impl.comment.fetchMany(critic, comment_ids)

def fetchAll(critic, review=None, author=None, comment_type=None, state=None,
             location_type=None, changeset=None, commit=None):
    """Fetch all Comment objects

       If |review| is not None, only comments in the specified review are
       returned.

       If |author| is not None, only comments created by the specified user are
       returned.

       If |comment_type| is not None, only comments of the specified type are
       returned.

       If |state| is not None, only issues in the specified state are returned.
       This implies type="issue".

       If |location_type| is not None, only issues in the specified type of
       location are returned.

       If |changeset| is not None, only comments against file versions that are
       referenced by the specified changeset are returned. Must be combined with
       |review|, and can not be combined with |commit|.

       If |commit| is not None, only comments against the commit's message or
       file versions referenced by the commit are returned. Must be combined
       with |review|, and can not be combined with |changeset|."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert review is None or isinstance(review, api.review.Review)
    assert author is None or isinstance(author, api.user.User)
    assert comment_type is None or comment_type in Comment.TYPE_VALUES
    assert state is None or state in Issue.STATE_VALUES
    assert state is None or comment_type in (None, "issue")
    assert location_type is None or location_type in Location.TYPE_VALUES
    assert changeset is None or isinstance(changeset, api.changeset.Changeset)
    assert changeset is None or review is not None
    assert commit is None or isinstance(commit, api.commit.Commit)
    assert commit is None or review is not None
    assert changeset is None or commit is None
    return api.impl.comment.fetchAll(critic, review, author, comment_type,
                                     state, location_type, changeset, commit)
