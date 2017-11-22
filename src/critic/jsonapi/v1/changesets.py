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

import logging
from typing import (
    Awaitable,
    Collection,
    Literal,
    Optional,
    overload,
    Sequence,
    TypedDict,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi

Files = jsonapi.ValueWrapper[Collection[api.filechange.FileChange]]
ContributingCommits = jsonapi.ValueWrapper[Collection[api.commit.Commit]]

Comments = Sequence[api.comment.Comment]
ReviewableFileChanges = jsonapi.ValueWrapper[
    Collection[api.reviewablefilechange.ReviewableFileChange]
]
ReviewState = TypedDict(
    "ReviewState",
    {
        "review": api.review.Review,
        "comments": Awaitable[Optional[Comments]],
        "reviewablefilechanges": Awaitable[Optional[ReviewableFileChanges]],
    },
)

JSONResult = TypedDict(
    "JSONResult",
    {
        "id": int,
        "completion_level": Awaitable[Collection[api.changeset.CompletionLevel]],
        "repository": Awaitable[api.repository.Repository],
        "from_commit": Awaitable[Optional[api.commit.Commit]],
        "to_commit": Awaitable[api.commit.Commit],
        "is_direct": Awaitable[bool],
        "is_replay": bool,
        "files": Awaitable[Optional[Files]],
        "contributing_commits": Awaitable[Optional[ContributingCommits]],
        "review_state": Awaitable[Optional[ReviewState]],
    },
)


class Changesets(
    jsonapi.ResourceClass[api.changeset.Changeset], api_module=api.changeset
):
    """Changesets in the git repositories"""

    name = "changesets"
    contexts = (None, "repositories", "reviews")
    value_class = api.changeset.Changeset
    exceptions = (api.changeset.Error,)

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.changeset.Changeset
    ) -> JSONResult:
        """Changeset {
             "id": integer, // the changeset's id
             "type": string, // the changeset type (direct, custom, merge,
                             // conflict)
             "from_commit": integer, // commit id for changesets from_commit
             "to_commit": integer, // commit id for changesets to_commit
             "files": integer[], // a list of all files changed in this
                                 // changeset
             "review_state": ReviewState or null,
           }

           ReviewState {
             "review": integer,
             "comments": integer[],
           }"""

        async def files() -> Optional[Files]:
            files = await value.files
            if files is None:
                return None
            return jsonapi.basic_list(
                sorted(files, key=lambda filechange: filechange.file.id)
            )

        async def review_state() -> Optional[ReviewState]:
            review = await Reviews.deduce(parameters)

            if not review:
                return None

            async def comments() -> Comments:
                return await api.comment.fetchAll(
                    parameters.critic, review=review, changeset=value
                )

            async def reviewablefilechanges() -> Optional[ReviewableFileChanges]:
                assert review
                try:
                    return await jsonapi.sorted_by_id(
                        await api.reviewablefilechange.fetchAll(review, changeset=value)
                    )
                except api.reviewablefilechange.InvalidChangeset:
                    return None

            return {
                "review": review,
                "comments": comments(),
                "reviewablefilechanges": reviewablefilechanges(),
            }

        async def contributing_commits() -> Optional[ContributingCommits]:
            commitset = await value.contributing_commits
            if commitset is None:
                return None
            return jsonapi.basic_list(list(commitset.topo_ordered))

        return {
            "id": value.id,
            "completion_level": value.completion_level,
            "repository": value.repository,
            "from_commit": value.from_commit,
            "to_commit": value.to_commit,
            "is_direct": value.is_direct,
            "is_replay": value.is_replay,
            "files": files(),
            "contributing_commits": contributing_commits(),
            "review_state": review_state(),
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.changeset.Changeset:
        """Retrieve one (or more) changesets.

           CHANGESET_ID : integer

           Retrieve a changeset identified by its unique numeric id."""

        changeset = await api.changeset.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

        only_if_complete_parameter = parameters.getQueryParameter("only_if_complete")
        if only_if_complete_parameter is not None:
            try:
                only_if_complete = set(
                    api.changeset.as_completion_level(item)
                    for item in only_if_complete_parameter.split(",")
                )
            except api.changeset.Error as error:
                raise jsonapi.UsageError(
                    f"Invalid 'only_if_complete' parameter: {error}"
                )
            if only_if_complete - await changeset.completion_level:
                raise jsonapi.ResultDelayed("Incomplete changeset")

        return changeset

    @staticmethod
    async def multiple(parameters: jsonapi.Parameters) -> api.changeset.Changeset:
        """Retrieve (and create if it doesn't exist) a changeset identified by
           a single commit (changeset type: direct) or any two commits in the
           same repository (changeset type: custom).

           from : COMMIT_SHA1 : string

           Retrieve a changeset with a commit (identified by its SHA-1 sum) as
           its from_commit. The SHA-1 sum can be abbreviated, but must be at
           least 4 characters long, and must be unambiguous in the repository.
           Must be used together with parameter 'to'.

           to : COMMIT_SHA1 : string

           Retrieve a changeset with a commit (identified by its SHA-1 sum) as
           its to_commit. The SHA-1 sum can be abbreviated, but must be at least
           4 characters long, and must be unambiguous in the repository. Must be
           used together with parameter 'from'.

           commit : COMMIT_SHA1 : string

           Retrieve a changeset with a commit (identified by its SHA-1 sum) as
           its to_commit, and the commit's parent as its from_commit. The SHA-1
           sum can be abbreviated, but must be at least 4 characters long, and
           must be unambiguous in the repository. Cannot be combined with 'from'
           or 'to'. The commit can not be a merge commit; in that case, the
           'v1/mergeanalyses' end-point should be used instead.

           repository : REPOSITORY : -

           Specify repository to access, identified by its unique numeric id or
           short-name.  Required unless a repository is specified in the
           resource path.

           review : REVIEW_ID : -

           Specify a review to calculate an "automatic" changeset for.

           automatic : MODE : string

           Calculate the changeset commit range automatically based on a review
           and a mode, which must be "everything", "reviewable" (changes
           assigned to current user), "relevant" (changes assigned to or files
           watched by current user) or "pending" (unreviewed changes assigned to
           current user.)

           A review must be specified in this case, and none of the 'from', 'to'
           or 'commit' parameters can be used."""

        repository = await Repositories.deduce(parameters)
        if repository is None:
            raise jsonapi.UsageError(
                "repository needs to be specified, ex. &repository=<id>"
            )

        async def get_commit(name: str) -> Optional[api.commit.Commit]:
            return await Commits.fromParameter(parameters, name)

        from_commit = await get_commit("from")
        to_commit = await get_commit("to")
        single_commit = await get_commit("commit")

        review = await Reviews.deduce(parameters)
        automatic_parameter = parameters.getQueryParameter("automatic")

        if automatic_parameter is not None:
            try:
                automatic = api.changeset.as_automatic_mode(automatic_parameter)
            except api.changeset.Error as error:
                raise jsonapi.UsageError(f"Invalid automatic mode: {error}")
            if review is None:
                raise jsonapi.UsageError(
                    "A review must be specified when an automatic mode is used"
                )
            if from_commit or to_commit or single_commit:
                raise jsonapi.UsageError(
                    "Explicit commit range cannot be specified when an automatic mode "
                    "is used"
                )
            return await api.changeset.fetchAutomatic(review, automatic)

        if not (from_commit or to_commit or single_commit):
            raise jsonapi.UsageError(
                "Missing required parameters from and to, or commit"
            )

        if (from_commit is None) != (to_commit is None):
            raise jsonapi.UsageError(
                "Missing required parameters from and to, only one supplied"
            )

        if from_commit == to_commit and from_commit is not None:
            raise jsonapi.UsageError("from and to can't be the same commit")

        if single_commit and single_commit.is_merge:
            raise jsonapi.PathError(
                "Single commit is a merge commit", code="MERGE_COMMIT"
            )

        critic = parameters.critic

        if from_commit and to_commit:
            return await api.changeset.fetch(
                critic, from_commit=from_commit, to_commit=to_commit
            )
        else:
            assert single_commit
            return await api.changeset.fetch(critic, single_commit=single_commit)

    @overload
    @staticmethod
    async def deduce(
        parameters: jsonapi.Parameters,
    ) -> Optional[api.changeset.Changeset]:
        ...

    @overload
    @staticmethod
    async def deduce(
        parameters: jsonapi.Parameters, *, required: Literal[True]
    ) -> api.changeset.Changeset:
        ...

    @staticmethod
    async def deduce(
        parameters: jsonapi.Parameters, *, required: bool = False
    ) -> Optional[api.changeset.Changeset]:
        changeset = parameters.context.get(Changesets.name)
        changeset_parameter = parameters.getQueryParameter("changeset")
        if changeset_parameter is not None:
            if changeset is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: changeset=%s" % changeset_parameter
                )
            changeset_id = jsonapi.numeric_id(changeset_parameter)
            changeset = await api.changeset.fetch(parameters.critic, changeset_id)
        if required and not changeset:
            raise jsonapi.UsageError.missingParameter("changeset")
        return changeset

    @staticmethod
    async def setAsContext(
        parameters: jsonapi.Parameters, changeset: api.changeset.Changeset
    ) -> None:
        parameters.setContext(Changesets.name, changeset)


from .commits import Commits
from .repositories import Repositories
from .reviews import Reviews
