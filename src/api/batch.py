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

class BatchError(api.APIError):
    pass

class InvalidBatchId(BatchError):
    """Raised when an invalid batch id is used."""

    def __init__(self, batch_id):
        """Constructor"""
        super(InvalidBatchId, self).__init__("Invalid batch id: %d" % batch_id)

class Batch(api.APIObject):
    @property
    def id(self):
        """The batch's unique id, or None for unsubmitted changes"""
        return self._impl.id

    @property
    def is_empty(self):
        """True if the batch contains no changes"""
        return self._impl.isEmpty(self.critic)

    @property
    def review(self):
        """The review to which changes were submitted"""
        return self._impl.getReview(self.critic)

    @property
    def author(self):
        """The author of the changes in the batch

           The author is returned as an api.user.User object."""
        return self._impl.getAuthor(self.critic)

    @property
    def timestamp(self):
        """The time of submission, or None for unsubmitted changes

           The timestamp is returned as a datetime.datetime object."""
        return self._impl.timestamp

    @property
    def comment(self):
        """The author's overall comment

           The comment is returned as an api.comment.Note object, or None if the
           author did not provide a comment."""
        return self._impl.getComment(self.critic)

    @property
    def created_comments(self):
        """Created comments

           The comments are returned as a set of api.comment.Comment objects."""
        return self._impl.getCreatedComments(self.critic)

    @property
    def written_replies(self):
        """Written replies

           The replies are returned as a set of api.reply.Reply objects."""
        return self._impl.getWrittenReplies(self.critic)

    @property
    def resolved_issues(self):
        """Resolved issues

           The issues are returned as a set of api.comment.Comment objects. Note
           that the comment objects represent the current state, and that they
           may be api.comment.Note objects, and if they are api.comment.Issue
           objects, that their `state` attribute will not necessarily be
           "resolved"."""
        return self._impl.getResolvedIssues(self.critic)

    @property
    def reopened_issues(self):
        """Reopened issues

           The issues are returned as a set of api.comment.Comment objects. Note
           that the comment objects represent the current state, and that they
           may be api.comment.Note objects, and if they are api.comment.Issue
           objects, that their `state` attribute will not necessarily be
           "open"."""
        return self._impl.getReopenedIssues(self.critic)

    @property
    def morphed_comments(self):
        """Morphed comments (comments whose types was changed)

           The comments are returned as a dictionary mapping api.comment.Comment
           objects to their new type as a string ("issue" or "note".) Note that
           the comment object itself represents the current state, and its type
           will not necessarily match the new type it's mapped to."""
        return self._impl.getMorphedComments(self.critic)

    @property
    def reviewed_file_changes(self):
        """Reviewed file changes

           The reviewed changes are returned as a set of
           api.reviewablefilechanges.ReviewableFileChanges objects. Note that
           the file changes objects represent the current state, and their
           `reviewed_by` attribute will not necessarily be the author of this
           batch."""
        return self._impl.getReviewedFileChanges(self.critic)

    @property
    def unreviewed_file_changes(self):
        """Unreviewed file changes

           The unreviewed changes are returned as a set of
           api.reviewablefilechanges.ReviewableFileChanges objects. Note that
           the file changes objects represent the current state, and their
           `reviewed_by` attribute will not necessarily be None."""
        return self._impl.getUnreviewedFileChanges(self.critic)

def fetch(critic, batch_id):
    """Fetch the Batch object with the given id"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(batch_id, int)
    return api.impl.batch.fetch(critic, batch_id)

def fetchAll(critic, review=None, author=None):
    """Fetch all Batch objects

       If |review| is not None, only batches in the specified review are
       returned.

       If |author| is not None, only batches authored by the specified user are
       returned."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert review is None or isinstance(review, api.review.Review)
    assert author is None or isinstance(author, api.user.User)
    return api.impl.batch.fetchAll(critic, review, author)

def fetchUnpublished(critic, review):
    """Fetch a Batch object representing current unpublished changes

       The Batch object's |id| and |timestamp| objects will be None to signal
       that the object does not represent a real object. If the current user has
       no unpublished changes, the object's |is_empty| attribute will be true.

       Only the currently authenticated user's unpublished changes are
       returned."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(review, api.review.Review)
    return api.impl.batch.fetchUnpublished(critic, review)
