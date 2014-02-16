import api

class PartitionError(api.APIError):
    """Raised for incompatible commits/rebases arguments to create()"""
    pass

class Partition(api.APIObject):
    """Representation of a part of a disjoint commit log

       The history of a branch (such as a review branch) that has potentially
       been rebased one or more times during its existence, is represented as a
       linked list of "partitions" where each partition represents a connected
       set of commits and each "link" or "edge" between represents the branch
       being rebased."""

    class Edge(object):
        """The edge (in one direction) between two partitions"""

        def __init__(self, rebase, partition):
            self.__rebase = rebase
            self.__partition = partition

        @property
        def rebase(self):
            """The rebase between the partitions"""
            return self.__rebase

        @property
        def partition(self):
            """The other partition"""
            return self.__partition

    @property
    def preceding(self):
        """The edge leading to the preceding (newer) partition"""
        return self._impl.preceding

    @property
    def following(self):
        """The edge leading to the following (older) partition"""
        return self._impl.following

    @property
    def commits(self):
        """The set of commits in the partition

           The return value is an api.commitset.CommitSet object."""
        return self._impl.commits

def create(critic, commits, rebases=[]):
    """Divide a set of commits into partitions and return the first"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    if not isinstance(commits, api.commitset.CommitSet):
        commits = list(commits)
        assert all(isinstance(commit, api.commit.Commit) for commit in commits)
    rebases = list(rebases)
    assert all(isinstance(rebase, api.log.rebase.Rebase) for rebase in rebases)
    return api.impl.log.partition.create(critic, commits, rebases)
