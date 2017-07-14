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

class RepositoryError(api.APIError):
    """Base exception for all errors related to the Repository class"""
    pass

class InvalidRepositoryId(RepositoryError):
    """Raised when an invalid repository id is used"""

    def __init__(self, repository_id):
        """Constructor"""
        super(InvalidRepositoryId, self).__init__(
            "Invalid repository id: %r" % repository_id)

class InvalidRepositoryName(RepositoryError):
    """Raised when an invalid repository name is used"""

    def __init__(self, name):
        """Constructor"""
        super(InvalidRepositoryName, self).__init__(
            "Invalid repository name: %r" % name)

class InvalidRepositoryPath(RepositoryError):
    """Raised when an invalid repository path is used"""

    def __init__(self, path):
        """Constructor"""
        super(InvalidRepositoryPath, self).__init__(
            "Invalid repository path: %r" % path)

class InvalidRef(RepositoryError):
    """Raised by Repository.resolveRef() for invalid refs"""

    def __init__(self, ref):
        """Constructor"""
        super(InvalidRef, self).__init__("Invalid ref: %r" % ref)
        self.ref = ref

class GitCommandError(RepositoryError):
    """Raised by Repository methods when 'git' fails unexpectedly"""

    def __init__(self, argv, returncode, stdout, stderr):
        self.argv = argv
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

class Repository(api.APIObject):
    """Representation of one of Critic's repositories"""

    def __int__(self):
        return self.id

    @property
    def id(self):
        """The repository's unique id"""
        return self._impl.id

    @property
    def name(self):
        """The repository's short name"""
        return self._impl.name

    @property
    def path(self):
        """The repository's (absolute) file-system path"""
        return self._impl.path

    @property
    def url(self):
        """The repository's URL

           The URL type depends on the effective user's 'repository.urlType'
           setting."""
        return self._impl.getURL(self.critic)

    def resolveRef(self, ref, expect=None, short=False):
        """Resolve the given ref to a SHA-1 using 'git rev-parse'

           If 'expect' is not None, it should be a string containing a Git
           object type, such as "commit", "tag", "tree" or "blob".  When given,
           it is passed on to 'git rev-parse' using the "<ref>^{<expect>}"
           syntax.

           If 'short' is True, 'git rev-parse' is given the '--short' argument,
           which causes it to return a shortened SHA-1.  If 'short' is an int,
           it is given as the argument value: '--short=N'.

           If the ref can't be resolved, an InvalidRef exception is raised."""
        assert expect is None or expect in ("blob", "commit", "tag", "tree")
        return self._impl.resolveRef(str(ref), expect, short)

    def listCommits(self, include=None, exclude=None, args=None, paths=None):
        """List commits using 'git rev-list'

           Call 'git rev-list' to list commits reachable from the commits in
           'include' but not reachable from the commits in 'exclude'.  Extra
           arguments to 'git rev-list' can be added through 'args' or 'paths'.

           The return value is a list of api.commit.Commit objects."""
        if include is None:
            include = []
        elif isinstance(include, api.commit.Commit):
            include = [include]
        else:
            include = list(include)
        if exclude is None:
            exclude = []
        elif isinstance(exclude, api.commit.Commit):
            exclude = [exclude]
        else:
            exclude = list(exclude)
        args = [] if args is None else list(args)
        paths = [] if paths is None else list(paths)
        assert all(isinstance(commit, api.commit.Commit) for commit in include)
        assert all(isinstance(commit, api.commit.Commit) for commit in exclude)
        assert all(isinstance(arg, basestring) for arg in args)
        assert all(isinstance(path, basestring) for path in paths)
        return self._impl.listCommits(self, include, exclude, args, paths)

def fetch(critic, repository_id=None, name=None, path=None):
    """Fetch a Repository object with the given id, name or path"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert sum((repository_id is None, name is None, path is None)) == 2
    return api.impl.repository.fetch(critic, repository_id, name, path)

def fetchAll(critic):
    """Fetch Repository objects for all repositories

       The return value is a list ordered by the repositories' names."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    return api.impl.repository.fetchAll(critic)

def fetchHighlighted(critic, user):
    """Fetch Repository objects for repositories that are extra relevant

       The return value is a list ordered by the repositories' names."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(user, api.user.User)
    return api.impl.repository.fetchHighlighted(critic, user)
