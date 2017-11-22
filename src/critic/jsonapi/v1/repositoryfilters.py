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
from typing import Sequence, Optional, Union

from critic.api.reviewscope import ReviewScope

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi

RepositoryFilter = api.repositoryfilter.RepositoryFilter


async def modify(
    transaction: api.transaction.Transaction, filter: RepositoryFilter
) -> api.transaction.repositoryfilter.ModifyRepositoryFilter:
    return await transaction.modifyUser(await filter.subject).modifyFilter(filter)


class RepositoryFilters(
    jsonapi.ResourceClass[RepositoryFilter], api_module=api.repositoryfilter
):
    """Filters that apply to all changes in a repository."""

    contexts = (None, "users", "repositories")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: RepositoryFilter
    ) -> jsonapi.JSONResult:
        """Filter {
             "id": integer, // the filter's id
             "subject": integer, // the filter's subject (affected user)
             "type": string, // "reviewer", "watcher" or "ignored"
             "path": string, // the filtered path
             "repository": integer, // the filter's repository's id
             "delegates": integer[], // list of user ids
           }"""

        return {
            "id": value.id,
            "subject": value.subject,
            "repository": value.repository,
            "path": value.path,
            "type": value.type,
            "default_scope": value.default_scope,
            "scopes": value.scopes,
            "delegates": jsonapi.sorted_by_id(value.delegates),
        }

    @staticmethod
    async def single(parameters: jsonapi.Parameters, argument: str) -> RepositoryFilter:
        """Retrieve one (or more) of a user's repository filters.

           FILTER_ID : integer

           Retrieve a filter identified by the filters's unique numeric id."""

        filter = await api.repositoryfilter.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

        user = await Users.deduce(parameters)
        if user and user != filter.subject:
            raise jsonapi.PathError("Filter does not belong to specified user")

        repository = await Repositories.deduce(parameters)
        if repository and repository != filter.repository:
            raise jsonapi.PathError("Filter does not belong to specified repository")

        return filter

    @staticmethod
    async def multiple(parameters: jsonapi.Parameters) -> Sequence[RepositoryFilter]:
        """All repository filters.

           repository : REPOSITORY : -

           Include only filters for the specified repository, identified by its
           unique numeric id or short-name. Cannot be combined with |review|.

           review : REVIEW_ID : -

           Include only filters that apply to files touched by the specified
           review. Cannot be combined with |repository|.

           user : USER : -

           Include only filters belonging to the specified user (i.e. whose
           |subject| is the specified user.)

           file : FILE : -

           Include only filters that apply to the specified file. Must be
           combined with |repository|."""

        repository = await Repositories.deduce(parameters)
        review = await Reviews.deduce(parameters)
        subject = await Users.deduce(parameters)
        file = await Files.deduce(parameters)
        scope = await ReviewScopes.deduce(parameters)

        if repository and review:
            if repository != review.repository:
                raise jsonapi.UsageError("Repository and review cannot be combined")
            repository = None
        if file and not repository:
            raise jsonapi.UsageError("File must be combined with a repository")

        if repository:
            return await api.repositoryfilter.fetchAll(
                parameters.critic,
                subject=subject,
                repository=repository,
                file=file,
                scope=scope,
            )
        elif review:
            return await api.repositoryfilter.fetchAll(
                parameters.critic,
                subject=subject,
                review=review,
                file=file,
                scope=scope,
            )
        else:
            return await api.repositoryfilter.fetchAll(
                parameters.critic, subject=subject, scope=scope
            )

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> RepositoryFilter:
        from critic import reviewing

        class FilterPath(jsonapi.check.StringChecker):
            async def check(
                self,
                context: jsonapi.check.TypeCheckerContext,
                value: jsonapi.types.JSONInputItem,
            ) -> str:
                path = reviewing.filters.sanitizePath(
                    await super().check(context, value)
                )
                try:
                    reviewing.filters.validatePattern(path)
                except reviewing.filters.PatternError as error:
                    return str(error)
                return path

        critic = parameters.critic
        subject = await Users.deduce(parameters)
        repository = await Repositories.deduce(parameters)

        converted = await jsonapi.convert(
            parameters,
            {
                "subject?": api.user.User,
                "repository?": api.repository.Repository,
                "type": {"reviewer", "watcher", "ignored"},
                "path": FilterPath,
                "default_scope?": bool,
                "scopes?": [api.reviewscope.ReviewScope],
                "delegates?": [api.user.User],
            },
            data,
        )

        logger.debug("converted=%r", converted)

        if "subject" in converted:
            if subject and subject != converted["subject"]:
                raise jsonapi.UsageError("Ambiguous request: multiple users specified")
            subject = converted["subject"]
        if not subject:
            subject = critic.effective_user

        if "repository" in converted:
            if repository and repository != converted["repository"]:
                raise jsonapi.UsageError(
                    "Ambiguous request: multiple repositories specified"
                )
            repository = converted["repository"]
        elif repository is None:
            raise jsonapi.UsageError.missingInput("repository")
        assert repository

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.modifyUser(subject).createFilter(
                filter_type=converted["type"],
                repository=repository,
                path=converted["path"],
                default_scope=converted.get("default_scope", True),
                scopes=converted.get("scopes", []),
                delegates=converted.get("delegates", []),
            )

        return await modifier

    @staticmethod
    async def update(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[RepositoryFilter],
        data: jsonapi.JSONInput,
    ) -> None:
        converted = await jsonapi.convert(
            parameters, {"delegates": [api.user.User]}, data
        )
        delegates = converted["delegates"]

        async with api.transaction.start(parameters.critic) as transaction:
            for filter in values:
                (await modify(transaction, filter)).setDelegates(delegates)

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[RepositoryFilter]
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for filter in values:
                (await modify(transaction, filter)).delete()


from .files import Files
from .repositories import Repositories
from .reviews import Reviews
from .reviewscopes import ReviewScopes
from .users import Users
