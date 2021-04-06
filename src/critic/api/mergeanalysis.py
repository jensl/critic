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
from abc import abstractmethod

from typing import Awaitable, Callable, Collection, Mapping, Optional, Sequence

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="merge analysis"):
    pass


class Delayed(api.ResultDelayedError):
    pass


class MergeChangeset(api.APIObject):
    """Representation of the changes made by a merge compared to one parent"""

    @property
    @abstractmethod
    def merge(self) -> api.commit.Commit:
        """The merge commit"""
        ...

    @property
    @abstractmethod
    def parent(self) -> api.commit.Commit:
        """The merge parent commit that this changeset compares to"""
        ...

    @property
    @abstractmethod
    async def files(self) -> Optional[Collection[api.file.File]]:
        """The set of files that were modified by both sides of the merge

        The returned value is a set of api.file.File objects.

        The two sides of the merge referred to by "both sides" are
         1) between the merge-base and the parent, and
         2) between the parent and the merge commit.

        Note that only some, or none, of these files may have been changed on
        both sides in such a way that there was a conflict. Inclusion in this
        list simply means that the file has been modified at all."""
        ...

    @abstractmethod
    async def getMacroChunks(
        self, *, adjacency_limit: int = 2, context_lines: int = 3
    ) -> Mapping[api.file.File, Sequence[api.filediff.MacroChunk]]:
        """Return the "relevant" changes, given an "adjacency limit"

        The returned value is a dictionary mapping api.file.File objects to
        lists of api.filediff.MacroChunk objects.

        Only files included in the set returned by |files| can appear as keys
        in the dictionary, but all will not necessarily appear. The returned
        dictionary can also be empty, if there are no "relevant" changes to
        highlight at all.

        The "adjacency limit" determines what set of changes to include. It
        sets the maximum number of unchanged lines allowed between a block of
        changed lines in the diff between the merge-base commit and the
        parent commit, and a block of changed lines in the diff between the
        parent commit and the merge commit, for the latter block to be
        included in the returned filediff object. A zero limit means only
        overlapping or directly adjacent changes are included."""
        ...

    @abstractmethod
    async def ensure_availability(self, *, block: bool = True) -> bool:
        """Ensure (or check) the availability of linked data.

        Args:
            block (bool): `True` to ensure (blocking) and `False` to simply
                check.

        Returns:
            If `block` is `True`, then `True` is always returned. If `block` is
            `False`, then `True` is returned if all linked data is immediately
            available, and `False` if any subsequent accesses may raies
            critic.api.ResultDelayedError exceptions."""
        ...


class MergeAnalysis(api.APIObject):
    """Representation of the analysis of a merge commit"""

    @property
    @abstractmethod
    def merge(self) -> api.commit.Commit:
        ...

    @property
    @abstractmethod
    async def changes_relative_parents(self) -> Sequence[MergeChangeset]:
        """Filtered changes relative each parent.

        The returned value is a list of MergeChangeset objects, one for each
        parent of the merge commit, in the same order as the parents."""
        ...

    @property
    @abstractmethod
    async def conflict_resolutions(self) -> api.changeset.Changeset:
        """Conflict resolution changes.

        The value is an critic.api.changeset.Changeset object.

        The returned changeset compares the actual merge commit to a commit
        generated by Critic by running an equivalent `git merge` command, and
        committing the result without resolving any conflicts. The generated
        commit will be the old/left side of the diff, meaning the diff
        visualizes roughly how the worktree was modified by the merger to
        resolve the conflicts. Note though that the conflicts displayed may not
        be exactly the same as those seen by the merger, depending on what tools
        they used.

        This diff will also include, as direct changes, any modifications made
        to the worktree when performing the merge that were not made to resolve
        conflicts."""
        ...

    @abstractmethod
    async def ensure_availability(self, *, block: bool = True) -> bool:
        """Ensure (or check) the availability of linked data.

        Args:
            block (bool): `True` to ensure (blocking) and `False` to simply
                check.

        Returns:
            If `block` is `True`, then `True` is always returned. If `block` is
            `False`, then `True` is returned if all linked data is immediately
            available, and `False` if any subsequent accesses may raies
            critic.api.ResultDelayedError exceptions."""
        ...


async def fetch(merge: api.commit.Commit) -> MergeAnalysis:
    """Fetch the merge analysis for a merge commit.

    Args:
        merge (critic.api.commit.Commit): The merge commit.

    Returns:
        A `MergeAnalysis` object."""
    return await fetchImpl.get()(merge)


resource_name = "mergeanalyses"


fetchImpl: FunctionRef[
    Callable[[api.commit.Commit], Awaitable[MergeAnalysis]]
] = FunctionRef()
