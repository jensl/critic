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

class ReviewableFileChangeError(api.APIError):
    pass

class InvalidReviewableFileChangeId(ReviewableFileChangeError):
    """Raised when an invalid reviewable file change id is used"""
    def __init__(self, filechange_id):
        super(InvalidReviewableFileChangeId, self).__init__(
            "Invalid reviewable file change id: %d" % filechange_id)
        self.filechange_id = filechange_id

class InvalidReviewableFileChangeIds(ReviewableFileChangeError):
    """Raised when invalid reviewable file change ids are used"""
    def __init__(self, filechange_ids):
        super(InvalidReviewableFileChangeIds, self).__init__(
            "Invalid reviewable file change ids: %s"
            % ", ".join(map(str, filechange_ids)))
        self.filechange_ids = filechange_ids

class InvalidChangeset(ReviewableFileChangeError):
    """Raised when fetchAll() is called with an invalid changeset"""
    def __init__(self, changeset):
        super(InvalidChangeset, self).__init__(
            "Changeset has no reviewable changes: %d" % changeset.id)
        self.changeset = changeset

class ReviewableFileChange(api.APIObject):
    """Representation of changes to a file, to be reviewed"""

    @property
    def id(self):
        return self._impl.id

    @property
    def review(self):
        return self._impl.getReview(self.critic)

    @property
    def changeset(self):
        """The changeset that the change is part of

           The changeset is returned as an api.changeset.Changeset object. Note
           that this changeset is always of a single commit, and that this
           commit will be included in a partition in the review (meaning it will
           not be part of a rebased version of the review branch.)"""
        return self._impl.getChangeset(self.critic)

    @property
    def file(self):
        """The file that was changed

           The file is returned as an api.file.File object."""
        return self._impl.getFile(self.critic)

    @property
    def deleted_lines(self):
        """Number of deleted or modified lines

           In other words, number of lines in the old version of the file that
           are not present in the new version of the file."""
        return self._impl.deleted_lines

    @property
    def inserted_lines(self):
        """Number of modified or inserted lines

           In other words, number of lines in the new version of the file that
           were not present in the old version of the file."""
        return self._impl.inserted_lines

    @property
    def is_reviewed(self):
        """True if the file change has been marked as reviewed."""
        return self._impl.is_reviewed

    @property
    def reviewed_by(self):
        """The user that reviewed the changes

           The user is returned as a api.user.User object, or None if the change
           has not been reviewed yet."""
        return self._impl.getReviewedBy(self.critic)

    @property
    def assigned_reviewers(self):
        """The users that are assigned to review the changes

           The reviewers are returned as a set of api.user.User objects."""
        return self._impl.getAssignedReviewers(self.critic)

    class DraftChanges(object):
        """Draft changes to file change state"""

        def __init__(self, author, new_reviewed_by):
            self.__author = author
            self.__new_is_reviewed = new_reviewed_by is not None
            self.__new_reviewed_by = new_reviewed_by

        @property
        def author(self):
            """The author of these draft changes

               The author is returned as an api.user.User object."""
            return self.__author

        @property
        def new_is_reviewed(self):
            """New value for the |is_reviewed| attribute"""
            return self.__new_is_reviewed

        @property
        def new_reviewed_by(self):
            """New value for the |reviewed_by| attribute"""
            return self.__new_reviewed_by

    @property
    def draft_changes(self):
        """The file change's current draft changes

           The draft changes are returned as a ReviewableFileChange.DraftChanges
           object, or None if the current user has no unpublished changes to
           this file change."""
        return self._impl.getDraftChanges(self.critic)

def fetch(critic, filechange_id):
    """Fetch a single reviewable file change by its unique id"""
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(filechange_id, int)
    return api.impl.reviewablefilechange.fetch(critic, filechange_id)

def fetchMany(critic, filechange_ids):
    """Fetch multiple reviewable file change by their unique ids"""
    assert isinstance(critic, api.critic.Critic)
    filechange_ids = list(filechange_ids)
    assert all(isinstance(filechange_id, int)
               for filechange_id in filechange_ids)
    return api.impl.reviewablefilechange.fetchMany(critic, filechange_ids)

def fetchAll(critic, review, changeset=None, file=None, assignee=None,
             is_reviewed=None):
    """Fetch all reviewable file changes in a review

       If a |changeset| is specified, fetch only file changes that are part of
       that changeset.

       If a |file| is specified, fetch only file changes in that file.

       If a |assignee| is specified, fetch only file changes that the specified
       user is assigned to review.

       If |is_reviewed| is specified (not |None|), fetch only file changes that
       are marked as reviewed (when |is_reviewed==True|) or not."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(review, api.review.Review)
    assert changeset is None or isinstance(changeset, api.changeset.Changeset)
    assert file is None or isinstance(file, api.file.File)
    assert assignee is None or isinstance(assignee, api.user.User)
    assert is_reviewed is None or isinstance(is_reviewed, bool)
    return api.impl.reviewablefilechange.fetchAll(
        critic, review, changeset, file, assignee, is_reviewed)
