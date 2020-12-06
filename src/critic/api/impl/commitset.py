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

import collections
import logging
from typing import (
    Iterable,
    FrozenSet,
    Set,
    DefaultDict,
    Mapping,
    Sequence,
    Iterator,
    Optional,
    Collection,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)

from . import apiobject
from critic import api
from critic.api import commitset as public
from critic.gitaccess import SHA1

WrapperType = api.commitset.CommitSet


class CommitSet(apiobject.APIObject[WrapperType, Tuple[()], int]):
    wrapper_class = api.commitset.CommitSet

    commits: FrozenSet[api.commit.Commit]
    heads: FrozenSet[api.commit.Commit]
    tails: FrozenSet[api.commit.Commit]
    children: DefaultDict[SHA1, Set[api.commit.Commit]]
    parents: DefaultDict[SHA1, Set[api.commit.Commit]]

    def __init__(self, args: Tuple[()] = ()) -> None:
        self.commits = frozenset()
        self.heads = frozenset()
        self.tails = frozenset()
        self.children = collections.defaultdict(set)
        self.parents = collections.defaultdict(set)

    def setNow(
        self,
        commits: Iterable[api.commit.Commit],
        all_parents: Mapping[SHA1, Set[api.commit.Commit]],
    ) -> CommitSet:
        self.commits = frozenset(commits)

        parents: Set[api.commit.Commit] = set()
        for commit in self.commits:
            commit_parents = all_parents[commit.sha1]
            self.parents[commit.sha1] = commit_parents
            parents.update(commit_parents)
            for parent in commit_parents:
                self.children[parent.sha1].add(commit)

        self.heads = frozenset(self.commits - parents)
        self.tails = frozenset(parents - self.commits)

        return self

    async def set(self, commits: Iterable[api.commit.Commit]) -> CommitSet:
        self.commits = frozenset(commits)

        if not self.commits:
            return self

        commits_by_sha1 = {commit.sha1: commit for commit in self.commits}

        repository = next(iter(self.commits)).repository
        all_parent_sha1s: Set[SHA1] = set()
        tail_sha1s: DefaultDict[api.commit.Commit, Set[SHA1]] = collections.defaultdict(
            set
        )

        for commit in self.commits:
            assert repository == commit.repository
            parent_sha1s = commit.low_level.parents
            for parent_sha1 in parent_sha1s:
                parent = commits_by_sha1.get(parent_sha1)
                if parent:
                    self.parents[commit.sha1].add(parent)
                else:
                    tail_sha1s[commit].add(parent_sha1)
                self.children[parent_sha1].add(commit)
            all_parent_sha1s.update(parent_sha1s)

        if tail_sha1s:
            tails = {
                tail.sha1: tail
                for tail in await api.commit.fetchMany(
                    repository, sha1s=set.union(*tail_sha1s.values())
                )
            }
        else:
            tails = {}

        for commit, sha1s in tail_sha1s.items():
            for sha1 in sha1s:
                self.parents[commit.sha1].add(tails[sha1])

        self.heads = frozenset(
            commit for commit in self.commits if commit.sha1 not in all_parent_sha1s
        )
        self.tails = frozenset(tails.values())

        return self

    def __iter__(self) -> Iterator[api.commit.Commit]:
        return iter(self.commits)

    def __bool__(self) -> bool:
        return bool(self.commits)

    def __len__(self) -> int:
        return len(self.commits)

    def __contains__(self, item: Union[str, api.commit.Commit]) -> bool:
        return str(item) in self.commits

    def __hash__(self) -> int:
        return hash(self.commits)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CommitSet) and self.commits == other.commits

    async def getFilteredTails(
        self, critic: api.critic.Critic
    ) -> FrozenSet[api.commit.Commit]:
        if not self.commits:
            return frozenset()

        repository = next(iter(self.commits)).repository
        candidates: Set[api.commit.Commit] = set(self.tails)
        result: Set[api.commit.Commit] = set()

        while candidates:
            tail = candidates.pop()

            eliminated: Set[api.commit.Commit] = set()
            for other in candidates:
                try:
                    base = await repository.mergeBase(tail, other)
                    if base == tail:
                        # Tail is an ancestor of other: tail should not be
                        # included in the returned set.
                        break
                    elif base == other:
                        # Other is an ancestor of tail: other should not be
                        # included in the returned set.
                        eliminated.add(other)
                except api.repository.GitCommandError:
                    # 'git merge-base' fails if there is no common ancestor
                    # commit.
                    pass
            else:
                result.add(tail)
            candidates -= eliminated

        return frozenset(result)

    async def getUpstream(self, critic: api.critic.Critic) -> api.commit.Commit:
        try:
            (upstream,) = await self.getFilteredTails(critic)
        except ValueError:
            raise api.commitset.InvalidCommitRange() from None
        return upstream

    def getDateOrdered(self) -> Iterator[api.commit.Commit]:
        queue = sorted(
            self.commits, key=lambda commit: commit.committer.timestamp, reverse=True
        )
        included: Set[api.commit.Commit] = set()

        while queue:
            commit = queue.pop(0)
            if commit in included:
                continue
            if commit not in self.heads:
                remaining_children = self.getChildrenOf(commit) - included
                if remaining_children:
                    # Some descendants of this commit have not yet been emitted;
                    # we have to delay this commit.  Insert the commit after the
                    # earliest remaining descendant in the list.  This means
                    # that as soon as we've processed all descendants, we retry
                    # the commit.
                    queue.insert(
                        max(queue.index(child) for child in remaining_children) + 1,
                        commit,
                    )
                    continue
            yield commit
            included.add(commit)

    def getTopoOrdered(self) -> Iterator[api.commit.Commit]:
        if not self:
            return

        logger.debug(
            "commitset.topo_ordered: size=%d, parents=%r", len(self), self.parents
        )

        head = next(iter(self.heads))
        logger.debug("commitset.topo_ordered: head=%r", head)

        queue = [head]
        included: Set[api.commit.Commit] = set()

        while queue:
            commit = queue.pop(0)
            logger.debug("commitset.topo_ordered: commit=%r, queue=%r", commit, queue)
            if commit in included:
                continue
            if commit not in self.heads:
                if self.getChildrenOf(commit) - included:
                    # Some descendants of this commit have not yet been emitted;
                    # we have to delay this commit.  We can only delay this
                    # commit if the queue is non-empty, so assert that it isn't.
                    assert queue
                    queue.append(commit)
                    continue
            yield commit
            included.add(commit)
            logger.debug(
                "commitset.topo_ordered: getParentsOf()=%r", self.getParentsOf(commit)
            )
            parents = sorted(
                (
                    parent
                    for parent in self.getParentsOf(commit)
                    if parent not in included
                ),
                key=lambda commit: commit.committer.timestamp,
                reverse=False,
            )
            logger.debug("commitset.topo_ordered: parents=%r", parents)
            queue[:0] = parents

    def getChildrenOf(self, commit: api.commit.Commit) -> FrozenSet[api.commit.Commit]:
        return frozenset(self.children.get(commit.sha1, set()))

    def getParentsOf(self, commit: api.commit.Commit) -> FrozenSet[api.commit.Commit]:
        return frozenset(
            parent for parent in self.parents[commit.sha1] if parent in self
        )

    def getDescendantsOf(
        self, commits: Sequence[api.commit.Commit], include_self: bool
    ) -> WrapperType:
        descendants: Set[api.commit.Commit] = set()
        if include_self:
            descendants.update(commits)
        queue: Set[api.commit.Commit] = set()
        for commit in commits:
            queue.update(self.getChildrenOf(commit))
        while queue:
            descendant = queue.pop()
            descendants.add(descendant)
            children = self.getChildrenOf(descendant)
            if children:
                queue.update(children - descendants)
        return createNow(commits[0].critic, descendants, self.parents)

    def getAncestorsOf(
        self, commits: Sequence[api.commit.Commit], include_self: bool
    ) -> WrapperType:
        ancestors: Set[api.commit.Commit] = set()
        if include_self:
            ancestors.update(commits)
        queue: Set[api.commit.Commit] = set()
        for commit in commits:
            queue.update(self.getParentsOf(commit))
        while queue:
            ancestor = queue.pop()
            ancestors.add(ancestor)
            queue.update(set(self.getParentsOf(ancestor)) - ancestors)
        return createNow(commits[0].critic, ancestors, self.parents)

    async def union(
        self, critic: api.critic.Critic, commits: Iterable[api.commit.Commit]
    ) -> api.commitset.CommitSet:
        return await create(critic, self.commits.union(commits))

    def intersection(
        self, critic: api.critic.Critic, commits: Iterable[api.commit.Commit]
    ) -> api.commitset.CommitSet:
        return createNow(critic, self.commits.intersection(commits), self.parents)

    def difference(
        self, critic: api.critic.Critic, commits: Iterable[api.commit.Commit]
    ) -> api.commitset.CommitSet:
        return createNow(critic, self.commits.difference(commits), self.parents)

    async def symmetric_difference(
        self, critic: api.critic.Critic, commits: Iterable[api.commit.Commit]
    ) -> api.commitset.CommitSet:
        return await create(critic, self.commits.symmetric_difference(commits))

    def contains(self, commit: Union[SHA1, api.commit.Commit]) -> bool:
        if isinstance(commit, str):
            return commit in self.parents
        return commit in self.commits


def createNow(
    critic: api.critic.Critic,
    commits: Iterable[api.commit.Commit],
    all_parents: Mapping[SHA1, Set[api.commit.Commit]],
) -> WrapperType:
    return CommitSet().setNow(commits, all_parents).wrap(critic)


@public.emptyImpl
def empty(critic: api.critic.Critic) -> WrapperType:
    return CommitSet().wrap(critic)


@public.createImpl
async def create(
    critic: api.critic.Critic, commits: Iterable[api.commit.Commit]
) -> WrapperType:
    if isinstance(commits, api.commitset.CommitSet):
        return commits

    return (await CommitSet().set(commits)).wrap(critic)


@public.calculateFromRangeImpl
async def calculateFromRange(
    critic: api.critic.Critic,
    from_commit: Optional[api.commit.Commit],
    to_commit: api.commit.Commit,
) -> WrapperType:
    return await api.commit.fetchRange(from_commit=from_commit, to_commit=to_commit)


@public.calculateFromBranchUpdateImpl
async def calculateFromBranchUpdate(
    critic: api.critic.Critic,
    current_commits: Optional[WrapperType],
    from_commit: api.commit.Commit,
    to_commit: api.commit.Commit,
    force_include: Optional[Iterable[api.commit.Commit]],
) -> WrapperType:
    repository = from_commit.repository
    new_commits: Set[api.commit.Commit] = set()

    _current_commits: Collection[api.commit.Commit]
    if current_commits:
        _current_commits = current_commits
    else:
        _current_commits = ()

    force_include_set = set(force_include) if force_include else set()

    async def traverse(
        commit: api.commit.Commit,
        *,
        restricted_to: Optional[Set[api.commit.Commit]] = None
    ) -> None:
        while True:
            # Stop when we reach |from_commit|, a commit in
            # |current_commits|, or a commit we've already processed.
            if (
                commit == from_commit
                or commit in _current_commits
                or commit in new_commits
                or (restricted_to and commit not in restricted_to)
            ):
                return

            # Add this commit and consider its parents.
            new_commits.add(commit)

            parents = await commit.parents

            if len(parents) == 1:
                # Optimization: No need to be clever about non-merges.
                commit = parents[0]
                continue

            if _current_commits:
                # Updated branch mode: Add (and traverse) any parent whose
                # merge-base with |from_commit| is already part of the branch.
                for parent in parents:
                    if parent not in _current_commits:
                        base = await repository.mergeBase(from_commit, parent)
                        if base not in _current_commits:
                            if parent in force_include_set:
                                await traverse(parent, restricted_to=force_include_set)
                            continue
                    await traverse(parent)
            else:
                # Created or rebased branch mode: Add (and traverse) the first
                # parent that is a descendent of |from_commit| (called
                # |key_parent|) and any subsequent parent that also is, and
                # whose merge-base with |key_parent| isn't |from_commit|.
                #
                # Put differently, we only want to include commits based on
                # |from_commit|, and only one immediate child of |from_commit|.
                # We let the first (included) parent of a each merge decide
                # which path to take to |from_commit|.
                key_parent = None
                for parent in parents:
                    if not await from_commit.isAncestorOf(parent):
                        continue
                    if not key_parent:
                        key_parent = parent
                    else:
                        base = await repository.mergeBase(key_parent, parent)
                        if base == from_commit:
                            continue
                    await traverse(parent)

            break

    await traverse(to_commit)

    assert not (force_include_set - new_commits), repr((force_include_set, new_commits))

    return await create(critic, new_commits)
