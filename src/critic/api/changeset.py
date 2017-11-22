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

from __future__ import annotations

from typing import Optional, Sequence, Literal, FrozenSet, Set, Iterable, overload, cast

from critic import api


class Error(api.APIError, object_type="changeset"):
    pass


class ChangesetBackgroundServiceError(Error):
    pass


class InvalidId(api.InvalidIdError, Error):
    pass


class NotImplementedError(Error):
    pass


class Delayed(api.ResultDelayedError):
    pass


class AutomaticChangesetEmpty(Error):
    """Raised when fetching an automatic changeset, and no changes were found"""

    pass


AutomaticMode = Literal["everything", "relevant", "reviewable", "pending"]
AUTOMATIC_MODES: FrozenSet[AutomaticMode] = frozenset(
    [
        # All changes in the review.
        "everything",
        # All changes in the review that are either assigned to the current user
        # or that matches one of the current user's watcher filters.
        "relevant",
        # All changes in the review that are assigned to the current user.
        "reviewable",
        # All pending changes in the review that are assigned to the current
        # user.
        "pending",
    ]
)


def as_automatic_mode(value: str) -> AutomaticMode:
    if value not in AUTOMATIC_MODES:
        raise Error(f"invalid automatic mode: {value!r}")
    return cast(AutomaticMode, value)


CompletionLevel = Literal[
    "structure", "changedlines", "analysis", "syntaxhighlight", "full",
]
COMPLETION_LEVELS: FrozenSet[CompletionLevel] = frozenset(
    {
        # All api.filechange.FileChange objects are available.
        "structure",
        # Counts/blocks of deleted/inserted lines per file is available.
        "changedlines",
        # Blocks of changed lines are fully analysed.
        "analysis",
        # Syntax highlighting of all file versions is cached.
        "syntaxhighlight",
        # All of the above.
        "full",
    }
)


def as_completion_level(value: str) -> CompletionLevel:
    if value not in COMPLETION_LEVELS:
        raise Error(f"invalid completion level: {value!r}")
    return cast(CompletionLevel, value)


class Changeset(api.APIObject):
    """Representation of a diff"""

    def __str__(self) -> str:
        return str(self._impl.id) + " (" + str(self._impl.type) + ")"

    @property
    def id(self) -> int:
        return self._impl.id

    @property
    async def repository(self) -> api.repository.Repository:
        """The repository containing the compared commits"""
        return await self._impl.getRepository(self.critic)

    @property
    async def from_commit(self) -> Optional[api.commit.Commit]:
        return await self._impl.getFromCommit(self.critic)

    @property
    async def to_commit(self) -> api.commit.Commit:
        return await self._impl.getToCommit(self.critic)

    @property
    async def is_direct(self) -> bool:
        """True if this is a "direct" changeset

           A changeset is considered direct if it is between a commit and one of
           its immediate parent commits, in the natural direction (from parent
           to child.)"""
        return await self._impl.isDirect(self.critic)

    @property
    def is_replay(self) -> bool:
        """True if the `Changeset.from_commit` is a merge/rebase replay.

        The main significance of this is that this means the old side of commit
        is the result of "replaying" a merge or a review rebase, which means
        there might be checked in (added) conflict headers in this commit. Some
        custom syntax highlighting is applied to them, which is not applied in
        normal diffs."""
        return self._impl.is_replay

    @property
    async def files(self) -> Optional[Sequence[api.filechange.FileChange]]:
        if not self._impl.is_complete:
            return None
        return await api.filechange.fetchAll(self)

    @property
    async def contributing_commits(self) -> Optional[api.commitset.CommitSet]:
        return await self._impl.getContributingCommits(self.critic)

    @property
    async def completion_level(self) -> Set[CompletionLevel]:
        """Changeset processing completion level

           The completion level is returned as a set of identifiers from the
           COMPLETION_LEVELS set."""
        return await self._impl.getCompletionLevel(self)

    async def ensure(
        self, *completion_levels: CompletionLevel, block: bool = True
    ) -> bool:
        """Ensure complete processing of the changeset

           Zero or more completion levels can be specified to check for. If zero
           levels are specified, "full" is implied. All specified levels must be
           reached.

           If |block| is True, the returned coroutine blocks until the specified
           completion levels have been reached, and returns True. If |block| is
           False, the returned coroutine returns True if the specified
           completion levels has been reached, and False otherwise.

           Note: using this function with |block=False| is a more efficient way
           to check for an intermediate level than reading |completion_level|,
           since it can skip checks that are not needed to produce the requested
           answer."""
        assert all(
            completion_level in COMPLETION_LEVELS
            for completion_level in completion_levels
        )
        return await self._impl.ensure(
            self, frozenset(completion_levels or {"full"}), bool(block)
        )


@overload
async def fetch(critic: api.critic.Critic, changeset_id: int, /,) -> Changeset:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    from_commit: Optional[api.commit.Commit],
    to_commit: api.commit.Commit,
    conflicts: bool = False,
) -> Changeset:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    single_commit: api.commit.Commit,
    conflicts: bool = False,
) -> Changeset:
    ...


async def fetch(
    critic: api.critic.Critic,
    changeset_id: int = None,
    /,
    *,
    from_commit: api.commit.Commit = None,
    to_commit: api.commit.Commit = None,
    single_commit: api.commit.Commit = None,
    conflicts: bool = False,
) -> Changeset:
    """Fetch a single changeset from the given repository"""

    from .impl import changeset as impl

    if single_commit:
        assert len(await single_commit.parents) <= 1
    if from_commit and to_commit:
        assert from_commit != to_commit
        assert from_commit.repository == to_commit.repository
    return await impl.fetch(
        critic, changeset_id, from_commit, to_commit, single_commit, conflicts
    )


async def fetchAutomatic(
    review: api.review.Review, automatic: AutomaticMode
) -> Changeset:
    from .impl import changeset as impl

    return await impl.fetchAutomatic(review, automatic)


@overload
async def fetchMany(
    critic: api.critic.Critic, changeset_ids: Iterable[int], /
) -> Sequence[Changeset]:
    ...


@overload
async def fetchMany(
    critic: api.critic.Critic, /, *, branchupdate: api.branchupdate.BranchUpdate
) -> Sequence[Changeset]:
    ...


async def fetchMany(
    critic: api.critic.Critic,
    changeset_ids: Iterable[int] = None,
    *,
    branchupdate: api.branchupdate.BranchUpdate = None,
) -> Sequence[Changeset]:
    """Fetch multiple changesets

       If |branchupdate| is not None, it must represent an update of a review
       branch, and individual changesets for each of the commits added to the
       review because of the branch update are returned."""
    from .impl import changeset as impl

    if branchupdate is not None:
        assert (await branchupdate.branch).review is not None
    return await impl.fetchMany(critic, changeset_ids, branchupdate)


resource_name = table_name = "changesets"
