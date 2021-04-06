from __future__ import annotations
from abc import abstractmethod

from typing import Awaitable, Callable, Protocol, Iterable, Optional

from critic import api
from critic.api.apiobject import FunctionRef


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
        def rebase(self) -> api.rebase.Rebase:
            """The rebase between the partitions"""
            ...

        @property
        def partition(self) -> Partition:
            """The other partition"""
            ...

    @property
    @abstractmethod
    def preceding(self) -> Optional[Partition.Edge]:
        """The edge leading to the preceding (newer) partition"""
        ...

    @property
    @abstractmethod
    def following(self) -> Optional[Partition.Edge]:
        """The edge leading to the following (older) partition"""
        ...

    @property
    @abstractmethod
    def commits(self) -> api.commitset.CommitSet:
        """The set of commits in the partition

        The return value is an api.commitset.CommitSet object."""
        ...


async def create(
    critic: api.critic.Critic,
    commits: api.commitset.CommitSet,
    rebases: Iterable[api.rebase.Rebase] = [],
) -> Partition:
    """Divide a set of commits into partitions and return the first"""
    return await createImpl.get()(critic, commits, rebases)


createImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            api.commitset.CommitSet,
            Iterable[api.rebase.Rebase],
        ],
        Awaitable[Partition],
    ]
] = FunctionRef()
