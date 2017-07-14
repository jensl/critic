# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

class CommitError(api.APIError):
    pass

class InvalidCommitId(CommitError):
    """Raised when an invalid commit id is used"""
    def __init__(self, commit_id):
        super(InvalidCommitId, self).__init__(
            "Invalid commit id: %r" % commit_id)

class InvalidSHA1(CommitError):
    """Raised when a given SHA-1 is invalid as a commit reference"""
    def __init__(self, sha1):
        super(InvalidSHA1, self).__init__("Invalid commit SHA-1: %r" % sha1)
        self.sha1 = sha1

class NotAFile(CommitError):
    """Raised when attempting to access a non-file as a file"""
    def __init__(self, path):
        super(NotAFile, self).__init__("Path is not a file: %s" % path)
        self.path = path

class Commit(api.APIObject):
    """Representation of a Git commit"""

    def __str__(self):
        return self.sha1
    def __repr__(self):
        return "api.commit.Commit(sha1=%r)" % self.sha1
    def __hash__(self):
        return hash(str(self))
    def __eq__(self, other):
        return str(self) == str(other)

    @property
    def id(self):
        """The commit's unique database id"""
        return self._impl.getId(self.critic)

    @property
    def sha1(self):
        """The commit's full 40 character SHA-1"""
        return self._impl.sha1

    @property
    def tree(self):
        """The SHA-1 of the tree object referenced by the commit"""
        return self._impl.tree

    @property
    def summary(self):
        """The commit's single-line summary

           This is the first line of the commit message, unless that line starts
           with 'fixup!' or 'squash!', in which case the returned summary is the
           first non-empty line after that, with '[fixup] ' or '[squash] '
           prepended.  If there is no such non-empty line, the returned summary
           is just '[fixup]' or '[squash]'."""
        return self._impl.getSummary()

    @property
    def message(self):
        """The commit's full commit message"""
        return self._impl.message

    @property
    def parents(self):
        """The commit's parents

           The return value is a list of api.Commit objects."""
        return self._impl.getParents(self.critic)

    @property
    def description(self):
        """A string describing the commit in "friendly" way, or None

           This will typically be a tag name or a branch name; in the case of a
           branch name with "tip of" prepended if this commit is referenced
           directly by that branch."""
        return self._impl.getDescription(self.critic)

    class UserAndTimestamp(object):
        """Representation of the author or committer meta-data of a commit"""

        def __init__(self, name, email, timestamp):
            self.name = name
            self.email = email
            self.timestamp = timestamp

    @property
    def author(self):
        """The commit's "author" meta-data"""
        return self._impl.getAuthor(self.critic)

    @property
    def committer(self):
        """The commit's "committer" meta-data"""
        return self._impl.getCommitter(self.critic)

    def isAncestorOf(self, commit):
        """Return True if |self| is an ancestor of |commit|

           Also return True if |self| is |commit|, meaning a commit is
           considered an ancestor of itself."""
        assert isinstance(commit, Commit)
        return self._impl.isAncestorOf(commit)

    class FileInformation(object):
        """Basic information about a file in a commit"""

        def __init__(self, file, mode, sha1, size):
            self.__file = file
            self.__mode = mode
            self.__sha1 = sha1
            self.__size = size

        @property
        def file(self):
            """The represented file"""
            return self.__file

        @property
        def mode(self):
            """The file's "UNIX" mode as an integer"""
            # FIXME: Should we use an integer sub-class, like
            #        gitutils.Tree.Entry.Mode?
            return self.__mode

        @property
        def sha1(self):
            """The file content's SHA-1"""
            return self.__sha1

        @property
        def size(self):
            """The file's size in bytes"""
            return self.__size

    def getFileInformation(self, file):
        """Look up information about a file in the commit

           The entry is returned as an Commit.FileInformation object, or None if
           the path was not found in the commit's tree. If the path is found but
           is not a blob (e.g. because it's a directory), NotAFile is raised."""
        assert isinstance(file, api.file.File)
        return self._impl.getFileInformation(file)

    def getFileContents(self, file):
        """Fetch the blob (contents) of a file in the commit

           The return value is a string, or None if the path was not found in
           the commit's tree. If the path is found but is not a blob
           (e.g. because it is a directory), NotAFile is raised."""
        assert isinstance(file, api.file.File)
        return self._impl.getFileContents(file)

    def getFileLines(self, file):
        """Fetch the lines of a file in the commit

           Much like getFileContents(), but splits the returned string into a
           list of strings in a consistent way that matches how other parts of
           Critic treats line breaks, and thus compatible with stored line
           numbers.

           Note: commit.getFileContents(...).splitlines() is *not* correct!"""
        assert isinstance(file, api.file.File)
        return self._impl.getFileLines(file)

def fetch(repository, commit_id=None, sha1=None, ref=None):
    """Fetch a Git commit from the given repository

       The commit can be identified by its unique (internal) database id, its
       SHA-1 (full 40 character string) or by an arbitrary ref that resolves to
       a commit object (possibly via tag objects) when given to the
       'git rev-parse' command."""
    import api.impl
    assert isinstance(repository, api.repository.Repository)
    assert (ref is None) != ((commit_id is None) and (sha1 is None))
    return api.impl.commit.fetch(repository, commit_id, sha1, ref)
