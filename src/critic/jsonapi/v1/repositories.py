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
from typing import Sequence, Union, Optional

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess
from critic import jsonapi
from critic.background import gitaccessor


class Repositories(
    jsonapi.ResourceClass[api.repository.Repository], api_module=api.repository,
):
    """The Git repositories on this system."""

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.repository.Repository
    ) -> jsonapi.JSONResult:
        """Repository {
             "id": integer, // the repository's id
             "name": string, // the repository's (unique) short name
             "path": string, // relative file-system path
             "url": string, // the repository's URL
             "documentation_path": string or null,
           }"""

        result: jsonapi.JSONResult = {
            "id": value.id,
            "name": value.name,
            "path": value.path,
            "urls": value.urls,
            "documentation_path": value.documentation_path,
        }

        statistics_parameter = parameters.getQueryParameter("statistics")
        if statistics_parameter:
            statistics = await value.statistics
            if statistics_parameter == "default":
                result["statistics"] = {
                    "commits": statistics.commits,
                    "branches": statistics.branches,
                    "reviews": statistics.reviews,
                }
            else:
                raise jsonapi.UsageError("Invalid 'statistics' parameter")

        head_parameter = parameters.getQueryParameter("head")
        if head_parameter:
            include = set(head_parameter.split(","))
            if not include.issubset({"all", "value", "commit", "branch"}):
                raise jsonapi.UsageError("Invalid 'head' parameter")
            head: jsonapi.JSONResult = {}
            if include.intersection({"all", "value"}):
                head["value"] = await value.head.value
            if include.intersection({"all", "commit"}):
                head["commit"] = await value.head.commit
            if include.intersection({"all", "branch"}):
                head["branch"] = await value.head.branch
            result["head"] = head

        return result

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.repository.Repository:
        """Retrieve one (or more) repositories on this system.

           REPOSITORY_ID : integer

           Retrieve a repository identified by its unique numeric id."""

        return await api.repository.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[api.repository.Repository, Sequence[api.repository.Repository]]:
        """Retrieve a single named repository or all repositories on this
           system.

           name : SHORT_NAME : string

           Retrieve a repository identified by its unique short-name.  This is
           equivalent to accessing /api/v1/repositories/REPOSITORY_ID with that
           repository's numeric id.  When used, any other parameters are
           ignored.

           filter : highlighted : -

           If specified, retrieve only "highlighted" repositories.  These are
           repositories that are deemed of particular interest for the signed-in
           user.  (If no user is signed in, no repositories are highlighted.)"""

        critic = parameters.critic

        name_parameter = parameters.getQueryParameter("name")
        if name_parameter:
            return await api.repository.fetch(critic, name=name_parameter)
        filter_parameter = parameters.getQueryParameter("filter")
        if filter_parameter is not None:
            if filter_parameter == "highlighted":
                return await api.repository.fetchHighlighted(
                    critic, critic.effective_user
                )
            raise jsonapi.UsageError(
                "Invalid repository filter parameter: %r" % filter_parameter
            )
        repositories = await api.repository.fetchAll(critic)
        return repositories

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.repository.Repository:
        critic = parameters.critic

        converted = await jsonapi.convert(
            parameters,
            {
                "name": str,
                "path": str,
                "mirror?": {
                    "url": str,
                    "branches?": [{"remote_name": str, "local_name?": str}],
                    "tags?": bool,
                },
            },
            data,
        )

        name = api.repository.validateName(converted["name"])
        path = api.repository.validatePath(converted["path"])

        try:
            await api.repository.fetch(critic, name=name)
        except api.repository.InvalidName:
            pass
        else:
            raise jsonapi.UsageError(f"{name}: repository name already in use")

        try:
            await api.repository.fetch(critic, path=path)
        except api.repository.InvalidRepositoryPath:
            pass
        else:
            raise jsonapi.UsageError(f"{path}: repository path already in use")

        if converted.get("mirror"):
            mirror_url = converted["mirror"]["url"]
            mirror_branches = converted["mirror"].get("branches", [])
            mirror_tags = converted["mirror"].get("tags", False)

            gitrepository = gitaccessor.GitRepositoryProxy.make()
            refs = ["HEAD"]
            if mirror_branches:
                refs.extend(
                    "refs/heads/" + mirror_branch["remote_name"]
                    for mirror_branch in mirror_branches
                )
            try:
                remote_refs = await gitrepository.lsremote(
                    mirror_url, *refs, include_symbolic_refs=True
                )
            except gitaccess.GitProcessError:
                raise jsonapi.UsageError(
                    f"{mirror_url}: repository URL invalid or not accessible"
                )

            if mirror_branches:
                for mirror_branch in mirror_branches:
                    ref_name = "refs/heads/" + mirror_branch["remote_name"]
                    if ref_name not in remote_refs.refs:
                        raise jsonapi.UsageError(
                            f"refs/heads/{mirror_branch}: no such branch in "
                            "remote repository"
                        )
            elif "HEAD" in remote_refs.symbolic_refs:
                head_ref = remote_refs.symbolic_refs["HEAD"]
                if head_ref.startswith("refs/heads/"):
                    mirror_branches = [{"remote_name": head_ref[len("refs/heads/") :]}]

            if not mirror_branches and not mirror_tags:
                raise jsonapi.UsageError(
                    f"{mirror_url}: could not determine default branch to "
                    "mirror (empty repository?)"
                )
        else:
            mirror_url = mirror_branches = mirror_tags = None

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.createRepository(name, path)

            if mirror_branches:
                for mirror_branch in mirror_branches:
                    remote_name = mirror_branch["remote_name"]
                    await modifier.trackBranch(
                        mirror_url,
                        remote_name,
                        mirror_branch.get("local_name", remote_name),
                    )
            if mirror_tags:
                modifier.trackTags(mirror_url)

        return await modifier

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.repository.Repository],
    ) -> None:
        critic = parameters.critic

        async with api.transaction.start(critic) as transaction:
            for repository in values:
                await transaction.modifyRepository(repository).deleteRepository()

    @staticmethod
    async def deduce(
        parameters: jsonapi.Parameters,
    ) -> Optional[api.repository.Repository]:
        repository = parameters.context.get("repositories")
        repository_parameter = parameters.getQueryParameter("repository")
        if repository_parameter is not None:
            if repository is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: repository=%s" % repository_parameter
                )
            repository = await Repositories.fromParameterValue(
                parameters, repository_parameter
            )
        if repository is not None:
            return repository

        review = await Reviews.deduce(parameters)
        if review is not None:
            return await review.repository

        return None

    @staticmethod
    async def fromParameterValue(
        parameters: jsonapi.Parameters, value: str
    ) -> api.repository.Repository:
        repository_id, name = jsonapi.id_or_name(value)
        if repository_id is not None:
            return await api.repository.fetch(parameters.critic, repository_id)
        else:
            assert name is not None
            return await api.repository.fetch(parameters.critic, name=name)

    @staticmethod
    async def setAsContext(
        parameters: jsonapi.Parameters, repository: api.repository.Repository
    ) -> None:
        parameters.setContext(Repositories.name, repository)


from .reviews import Reviews
