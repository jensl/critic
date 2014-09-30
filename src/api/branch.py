import api

class BranchError(api.APIError):
    """Base exception for all errors related to the Branch class."""
    pass

class InvalidBranchId(BranchError):
    """Raised when an invalid branch id is used."""

    def __init__(self, branch_id):
        """Constructor"""
        super(InvalidBranchId, self).__init__(
            "Invalid branch id: %d" % branch_id)

class InvalidBranchName(BranchError):
    """Raised when an invalid branch name is used."""

    def __init__(self, name):
        """Constructor"""
        super(InvalidBranchName, self).__init__(
            "Invalid branch name: %r" % name)

class Branch(api.APIObject):
    """Representation of a Git branch, according to Critic

       Critic extends Git's branch concept by adding a heuristically determined
       base branch, and a derived restricted set of commits that belong to the
       branch by (initially) excluding those reachable from the base branch."""

    def __int__(self):
        return self.id
    def __hash__(self):
        return hash(int(self))
    def __eq__(self, other):
        return int(self) == int(other)

    @property
    def id(self):
        """The branch's unique id"""
        return self._impl.id

    @property
    def name(self):
        """The branch's name excluding the 'refs/heads/' prefix"""
        return self._impl.name

    @property
    def repository(self):
        """The repository that contains the branch

           The repository is returned as an api.repository.Repository object."""
        return self._impl.getRepository(self.critic)

    @property
    def head(self):
        """The branch's head commit"""
        return self._impl.getHead(self.critic)

    @property
    def commits(self):
        """The commits belonging to the branch

           The return value is an api.commitset.CommitSet object.

           Note: This set of commits is the commits that are actually reachable
                 from the head of the branch.  If the branch is a review branch
                 that has been rebased, this is not the same as the commits that
                 are considered part of the review."""
        return self._impl.getCommits(self.critic)

def fetch(critic, branch_id=None, repository=None, name=None):
    """Fetch a Branch object with the given id or name

       When a name is provided, a repository must also be provided."""
    import api.impl
    assert (branch_id is None) != (name is None)
    assert name is None or repository is not None
    return api.impl.branch.fetch(critic, branch_id, repository, name)

def fetchAll(critic, repository=None):
    """Fetch Branch objects for all branches

       If a repository is provided, restrict the return value to branches in the
       specified repository."""
    import api.impl
    assert (repository is None or
            isinstance(repository, api.repository.Repository))
    return api.impl.branch.fetchAll(critic, repository)
