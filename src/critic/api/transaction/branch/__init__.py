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

from typing import Iterable, Union, Optional, Tuple

from .. import LazyAPIObject, Transaction, protocol
from critic import api


async def validate_branch_name(
    repository: api.repository.Repository, name: str, *, ignore_conflict: str = None
) -> None:
    from ....background.githook.validaterefcreation import validate_ref_creation

    if ignore_conflict is not None:
        ignore_conflict = "refs/heads/" + ignore_conflict

    error = await validate_ref_creation(
        repository, "refs/heads/" + name, ignore_conflict=ignore_conflict
    )

    if error:
        raise api.branch.Error(f"Bad branch name: {error}", code="BAD_BRANCH_NAME")


async def validate_commit_set(
    critic: api.critic.Critic,
    head: Optional[api.commit.Commit],
    commits: Iterable[api.commit.Commit],
) -> Tuple[api.commitset.CommitSet, api.commit.Commit]:
    commitset = await api.commitset.create(critic, commits)

    if not commitset:
        assert head
        return api.commitset.empty(critic), head

    if len(commitset.heads) != 1:
        raise api.branch.Error("Invalid commit graph: not a single head commit")

    if head:
        assert head in commitset.heads
    else:
        (head,) = commitset.heads

    return commitset, head


class CreatedBranch(LazyAPIObject[api.branch.Branch], api_module=api.branch):
    def __init__(
        self,
        transaction: api.transaction.Transaction,
        commits: api.commitset.CommitSet,
        head: api.commit.Commit,
    ):
        super().__init__(transaction)
        self.__commits = commits
        self.__head = head

    @property
    async def commits(self) -> api.commitset.CommitSet:
        return self.__commits

    @property
    async def head(self) -> api.commit.Commit:
        return self.__head

    async def create_payload(
        self, resource_name: str, branch: api.branch.Branch, /
    ) -> protocol.CreatedAPIObject:
        return protocol.CreatedBranch(
            resource_name, branch.id, (await branch.repository).id, branch.name
        )


class CreatedBranchObject(LazyAPIObject):
    def __init__(
        self, transaction: Transaction, branch: Union[api.branch.Branch, CreatedBranch]
    ) -> None:
        super().__init__(transaction)
        self.branch = branch

    def scopes(self) -> LazyAPIObject.Scopes:
        return (f"branches/{int(self.branch)}",)


class CreatedBranchUpdate(CreatedBranchObject, api_module=api.branchupdate):
    pass


from .modify import ModifyBranch

__all__ = ["create_branch", "ModifyBranch"]
