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

from __future__ import annotations

from typing import Iterator, FrozenSet, Sequence, Union, Iterable, Optional

from critic import api


class InvalidCommitRange(Exception):
    """Raised by calculateFromRange() when the range is not simple

       Simple in this context means that the commit that defines the start of
       the range is an ancestor of the commit that defines the end of the range,
       and all commits in-between."""

    pass


class CommitSet(api.APIObject):
    """Representation of a set of Commit objects"""

    def __adapt__(self) -> Sequence[int]:
        return [int(commit) for commit in self]

    def __iter__(self) -> Iterator[api.commit.Commit]:
        return iter(self._impl)

    def __len__(self) -> int:
        return len(self._impl)

    def __contains__(self, item: object) -> bool:
        return isinstance(item, api.commit.Commit) and item in self._impl

    def __hash__(self) -> int:
        return hash(self._impl)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CommitSet) and self._impl == other._impl

    def __bool__(self) -> bool:
        return bool(self._impl)

    def __repr__(self) -> str:
        return "CommitSet(%r)" % list(self.topo_ordered)

    @property
    def date_ordered(self) -> Iterator[api.commit.Commit]:
        """The commits in the set in (commit) timestamp order

           The return value is a generator producing api.commit.Commit objects.
           Commits are guaranteed to precede their parents, even if the actual
           commit timestamp order is the opposite."""
        return self._impl.getDateOrdered()

    @property
    def topo_ordered(self) -> Iterator[api.commit.Commit]:
        """The commits in the set in "topological" order

           The return value is a generator producing api.commit.Commit objects.
           Commits are guaranteed to precede their parents, and as far as
           possible immediately precede their parent.

           It is only valid to call this function on commit sets with a single
           head (those whose 'heads' attribute returns a set of length 1.)"""
        assert not self or len(self.heads) == 1, repr(list(self))
        return self._impl.getTopoOrdered()

    @property
    def heads(self) -> FrozenSet[api.commit.Commit]:
        """The head commits of the set

           The return value is a frozenset of Commit objects.

           A "head commit" is defined as any commit in the set that is
           not an immediate parent of another commit in the set."""
        return self._impl.heads

    @property
    def tails(self) -> FrozenSet[api.commit.Commit]:
        """The tail commits of the set

           The return value is a frozenset of Commit objects.

           A "tail commit" is defined as any commit that is a parent of
           a commit in the set but isn't itself in the set."""
        return self._impl.tails

    @property
    async def filtered_tails(self) -> FrozenSet[api.commit.Commit]:
        """The filtered tail commits of the set

           The return value is a frozenset of Commit objects.

           The returned set will contain each tail commit that isn't an ancestor
           of another tail commit of the set. If the tail commits of the set are
           all different commits on an upstream branch, then this will only
           return the latest one."""

        return await self._impl.getFilteredTails(self.critic)

    @property
    async def upstream(self) -> api.commit.Commit:
        """The single "upstream" commit of the commit-set

        This is the single commit in the set returned by `filtered_tails`, when
        that set contains a single commit. If that set contains multiple
        commits, an `InvalidCommitRange` exception is raised instead."""
        return await self._impl.getUpstream(self.critic)

    def getChildrenOf(self, commit: api.commit.Commit) -> FrozenSet[api.commit.Commit]:
        """Return the commits in the set that are children of the commit

           The return value is a set of Commit objects."""
        return self._impl.getChildrenOf(commit)

    def getParentsOf(self, commit: api.commit.Commit) -> Sequence[api.commit.Commit]:
        """Return the intersection of the commit's parents and the set

           The return value is a list of Commit objects, in the same
           order as in "commit.parents"."""
        return self._impl.getParentsOf(commit)

    def getDescendantsOf(
        self,
        commit: Union[api.commit.Commit, Iterable[api.commit.Commit]],
        *,
        include_self: bool = False
    ) -> CommitSet:
        """Return the intersection of the commit's descendants and the set

           The return value is another CommitSet object.  If 'include_self' is
           True, the commit itself is included in the returned set.

           The argument can also be a iterable, in which case the returned set
           is the union of the sets that would be returned for each commit in
           the iterable."""
        if isinstance(commit, api.commit.Commit):
            commits = [commit]
        else:
            commits = list(commit)
        assert all(commit in self or commit in self.tails for commit in commits)
        return self._impl.getDescendantsOf(commits, include_self)

    def getAncestorsOf(
        self,
        commit: Union[api.commit.Commit, Iterable[api.commit.Commit]],
        *,
        include_self: bool = False
    ) -> CommitSet:
        """Return the intersection of the commit's ancestors and the set

           The return value is another CommitSet object.  If 'include_self' is
           True, the commit itself is included in the returned set.

           The argument can also be a iterable, in which case the returned set
           is the union of the sets that would be returned for each commit in
           the iterable."""
        if isinstance(commit, api.commit.Commit):
            commits = [commit]
        else:
            commits = list(commit)
        return self._impl.getAncestorsOf(commits, include_self)

    async def union(self, commits: Iterable[api.commit.Commit]) -> CommitSet:
        return await self._impl.union(self.critic, commits)

    def intersection(self, commits: Iterable[api.commit.Commit]) -> CommitSet:
        return self._impl.intersection(self.critic, commits)

    def __and__(self, commits: Iterable[api.commit.Commit]) -> CommitSet:
        return self.intersection(commits)

    def difference(self, commits: Iterable[api.commit.Commit]) -> CommitSet:
        return self._impl.difference(self.critic, commits)

    def __sub__(self, commits: Iterable[api.commit.Commit]) -> CommitSet:
        return self.difference(commits)

    async def symmetric_difference(
        self, commits: Iterable[api.commit.Commit]
    ) -> CommitSet:
        return await self._impl.symmetric_difference(self.critic, commits)


def empty(critic: api.critic.Critic) -> CommitSet:
    from .impl import commitset as impl

    assert isinstance(critic, api.critic.Critic)
    return impl.empty(critic)


async def create(
    critic: api.critic.Critic, commits: Iterable[api.commit.Commit]
) -> CommitSet:
    """Create a CommitSet object from an iterable of Commit objects"""
    from .impl import commitset as impl

    return await impl.create(critic, commits)


async def calculateFromRange(
    critic: api.critic.Critic,
    from_commit: Optional[api.commit.Commit],
    to_commit: api.commit.Commit,
) -> CommitSet:
    """Calculate a set of commits from a commit range"""
    from .impl import commitset as impl

    assert isinstance(critic, api.critic.Critic)
    assert from_commit is None or isinstance(from_commit, api.commit.Commit)
    assert isinstance(to_commit, api.commit.Commit)
    assert from_commit is None or from_commit.repository == to_commit.repository
    return await impl.calculateFromRange(critic, from_commit, to_commit)


async def calculateFromBranchUpdate(
    critic: api.critic.Critic,
    current_commits: Optional[CommitSet],
    from_commit: api.commit.Commit,
    to_commit: api.commit.Commit,
    force_include: Iterable[api.commit.Commit] = None,
) -> CommitSet:
    """Calculate set of commits to associate with branch when updating it

    If the branch is being created, |current_commits| should be None and
    |from_commit| should be the determined "upstream" commit. If the branch is
    being updated, |current_commits| should be the commits currently associated
    with the branch, and |from_commit| its pre-update tip.

    The rule of the calculation is that a commit reachable from |to_commit| is
    added if it is a descendant of |from_commit| or if its merge-base with
    |from_commit| is in |current_commits|. When processing a created branch,
    only one direct descendant of |from_commit| is included. If a merge is
    encountered where multiple parents are descendants of |from_commit| (and
    have no descendant of |from_commit| in common), only the first such parent
    is added.

    If |force_include| is not None, it should be a set of commits. Any commit in
    that set that is considered for inclusion but would be excluded by the rule
    described in the previous paragraph, is instead included. It is an error if
    any commit in the |force_include| set is never considered for inclusion at
    all, i.e. if the resulting set is not a super-set of |force_include|."""
    from .impl import commitset as impl

    assert isinstance(critic, api.critic.Critic)
    if current_commits is not None:
        if not isinstance(current_commits, CommitSet):
            current_commits = await create(critic, current_commits)
        assert from_commit in current_commits.heads or not current_commits
    assert isinstance(from_commit, api.commit.Commit)
    assert isinstance(to_commit, api.commit.Commit)
    assert force_include is None or isinstance(force_include, (set, CommitSet))
    return await impl.calculateFromBranchUpdate(
        critic, current_commits, from_commit, to_commit, force_include
    )
