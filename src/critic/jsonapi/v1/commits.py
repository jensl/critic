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

import logging
import re
from typing import Awaitable, Collection, Optional, Sequence, TypedDict, Union

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess
from critic.gitaccess import SHA1
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONResult
from ..utils import id_or_name, numeric_id
from .timestamp import timestamp


UserAndTimestamp = TypedDict(
    "UserAndTimestamp", {"name": str, "email": str, "timestamp": Awaitable[float]}
)


def user_and_timestamp(
    user_and_timestamp: api.commit.Commit.UserAndTimestamp,
) -> UserAndTimestamp:
    return {
        "name": user_and_timestamp.name,
        "email": user_and_timestamp.email,
        "timestamp": timestamp(user_and_timestamp.timestamp),
    }


class Commits(
    ResourceClass[api.commit.Commit],
    api_module=api.commit,
    exceptions=(api.commit.Error, api.repository.InvalidRef),
):
    """Commits in the Git repositories."""

    contexts = (None, "repositories", "changesets", "branches", "reviews")

    @staticmethod
    async def json(parameters: Parameters, value: api.commit.Commit) -> JSONResult:
        """Commit {
          "id": integer, // the commit's id
          "sha1": string, // the commit's SHA-1 sum
          "summary": string, // (processed) commit summary
          "message": string, // full / raw commit message
          "parents": [integer], // list of commit ids
          "tree": string, // SHA-1 sum of the commit's root tree object
          "author": {
            "name": string, // author (full)name
            "email": string, // author email
            "timestamp": float, // seconds since epoch
          },
          "committer": {
            "name": string, // committer (full)name
            "email": string, // committer email
            "timestamp": float, // seconds since epoch
          },
        }"""

        # Important:
        #
        # We're returning parents as integers instead of as api.commit.Commit
        # objects here, to disable expansion of them as linked objects.  Not
        # doing this would typically lead to recursively dumping all commits in
        # a repository a lot of the time, which wouldn't generally be useful.
        #
        # Limited sets of commits are returned as api.commit.Commit objects from
        # other resources, like reviews, which does enable expansion of them as
        # linked objects, just not recursively.
        async def parent_ids() -> Collection[int]:
            return [parent.id for parent in await value.parents]

        result: JSONResult = {
            "id": value.id,
            "sha1": value.sha1,
            "summary": value.summary,
            "message": value.message,
            "parents": parent_ids(),
            "tree": value.tree,
            "author": user_and_timestamp(value.author),
            "committer": user_and_timestamp(value.committer),
        }

        description_parameter = parameters.query.get("description")
        if description_parameter:
            description = await value.description
            if description_parameter == "default":
                result["description"] = {
                    "branch": description.branch,
                }
            else:
                raise UsageError("Invalid 'description' parameter")

        return result

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> api.commit.Commit:
        """Retrieve one (or more) commits from a Git repository.

        COMMIT_ID : integer

        Retrieve a commit identified by its unique numeric id.

        repository : REPOSITORY : -

        Specify repository to access, identified by its unique numeric id or
        short-name.  Required unless a repository is specified in the
        resource path."""

        repository = await parameters.deduce(api.repository.Repository)
        if repository is None:
            raise UsageError("Commit reference must have repository specified.")
        return await api.commit.fetch(repository, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Union[api.commit.Commit, Sequence[api.commit.Commit]]:
        """Retrieve a single commit identified by its SHA-1 sum.

        sha1 : COMMIT_SHA1 : string

        Retrieve a commit identified by its SHA-1 sum.  The SHA-1 sum can be
        abbreviated, but must be at least 4 characters long, and must be
        unambigious in the repository.

        repository : REPOSITORY : -

        Specify repository to access, identified by its unique numeric id or
        short-name.  Required unless a repository is specified in the
        resource path."""

        branch = await parameters.deduce(api.branch.Branch)
        if branch:
            return await Commits.fromBranch(parameters, branch)

        sha1_parameter = parameters.query.get("sha1")
        ref_parameter = parameters.query.get("ref")
        if sha1_parameter is None and ref_parameter is None:
            raise UsageError(
                "Missing parameter: one of 'sha1' and 'ref' must be specified."
            )
        sha1: Optional[SHA1]
        if sha1_parameter is not None:
            if not re.match("[0-9A-Fa-f]{4,40}$", sha1_parameter):
                raise UsageError("Invalid SHA-1 parameter: %r" % sha1_parameter)
            sha1 = gitaccess.as_sha1(sha1_parameter)
        else:
            sha1 = None
        repository = await parameters.deduce(api.repository.Repository)
        if repository is None:
            raise UsageError("Commit reference must have repository specified.")
        if sha1:
            return await api.commit.fetch(repository, sha1=sha1)
        else:
            assert ref_parameter is not None
            return await api.commit.fetch(repository, ref=ref_parameter)

    @staticmethod
    async def fromBranch(
        parameters: Parameters, branch: api.branch.Branch
    ) -> Sequence[api.commit.Commit]:
        after_update = await parameters.fromParameter(
            api.branchupdate.BranchUpdate, "after_update"
        )
        after_rebase = await parameters.fromParameter(api.rebase.Rebase, "after_rebase")

        if after_update and after_rebase:
            raise UsageError(
                "Conflicting parameters used: " "'after_update' and 'after_rebase'"
            )
        if after_rebase:
            after_update = await after_rebase.branchupdate
            if not after_update:
                raise UsageError(
                    "Invalid parameter: |after_rebase| " " (rebase is still pending)"
                )
        if after_update and branch != await after_update.branch:
            if after_rebase:
                raise UsageError(
                    "Invalid parameter: |after_rebase| "
                    "(rebase is not of this branch)"
                )
            raise UsageError(
                "Invalid parameter: |after_update| " "(update is not of this branch)"
            )

        sort_parameter = parameters.query.get("sort")
        if sort_parameter not in (None, "topological", "date"):
            raise UsageError("Invalid commits sort parameter: %r" % sort_parameter)

        scope = parameters.query.get("scope")

        if after_update:
            commits = await after_update.commits
        elif branch.type == "normal" and not await branch.base_branch:
            # A normal (non-review) branch without a base branch typically means
            # `master` or some similar branch, and may be assumed to contain
            # very many commits. Use some custom code to support a range request
            # without, accessing all reachable commits first.
            offset, end = parameters.getRange()
            count = end - offset if offset is not None and end is not None else None
            order: api.commit.Order = "topo" if sort_parameter != "date" else "date"
            head = await branch.head
            commits = await api.commit.fetchRange(
                to_commit=head, order=order, offset=offset, count=count
            )
            repository = await branch.repository
            parameters.setPagination(total=await repository.countCommits(include=head))
        else:
            commits = await branch.commits

        if scope == "upstreams":
            return list(await commits.filtered_tails)

        if sort_parameter is None or sort_parameter == "topological":
            return list(commits.topo_ordered)

        return list(commits.date_ordered)

    @classmethod
    async def deduce(cls, parameters: Parameters) -> Optional[api.commit.Commit]:
        commit = parameters.in_context(api.commit.Commit)
        commit_parameter = parameters.query.get("commit")
        if commit_parameter is not None:
            if commit is not None:
                raise UsageError.redundantParameter("commit")
            commit = await Commits.fromParameterValue(parameters, commit_parameter)
        return commit

    @staticmethod
    async def fromParameterValue(
        parameters: Parameters, value: str
    ) -> api.commit.Commit:
        repository = await parameters.deduce(api.repository.Repository)
        if not repository:
            raise UsageError("Commit reference must have repository specified.")
        commit_id, ref = id_or_name(value)
        if commit_id is not None:
            return await api.commit.fetch(repository, commit_id)
        assert ref is not None
        return await api.commit.fetch(repository, ref=ref)
