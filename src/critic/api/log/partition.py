from __future__ import annotations

from typing import Protocol, Iterable, Optional

from critic import api


class Error(api.APIError):
    """Raised for incompatible commits/rebases arguments to create()"""

    pass


class Partition(api.APIObject):
    """Representation of a part of a disjoint commit log

       The history of a branch (such as a review branch) that has potentially
       been rebased one or more times during its existence, is represented as a
       linked list of "partitions" where each partition represents a connected
       set of commits and each "link" or "edge" between represents the branch
       being rebased."""

    class Edge(Protocol):
        """The edge (in one direction) between two partitions"""

        @property
        def rebase(self) -> api.log.rebase.Rebase:
            """The rebase between the partitions"""
            ...

        @property
        def partition(self) -> Partition:
            """The other partition"""
            ...

    @property
    def preceding(self) -> Optional[Partition.Edge]:
        """The edge leading to the preceding (newer) partition"""
        return self._impl.preceding

    @property
    def following(self) -> Optional[Partition.Edge]:
        """The edge leading to the following (older) partition"""
        return self._impl.following

    @property
    def commits(self) -> api.commitset.CommitSet:
        """The set of commits in the partition

           The return value is an api.commitset.CommitSet object."""
        return self._impl.commits


async def create(
    critic: api.critic.Critic,
    commits: api.commitset.CommitSet,
    rebases: Iterable[api.log.rebase.Rebase] = [],
) -> Partition:
    """Divide a set of commits into partitions and return the first"""
    from ..impl.log import partition as impl

    return await impl.create(critic, commits, rebases)
