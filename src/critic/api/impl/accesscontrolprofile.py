# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

from dataclasses import dataclass
from typing import Optional, Tuple, Generic, TypeVar, Sequence

from critic import api
from .apiobject import APIObject

public = api.accesscontrolprofile
public_class = api.accesscontrolprofile.AccessControlProfile

# HTTPException = public_class.HTTPException
# RepositoryException = public_class.RepositoryException
# ExtensionException = public_class.ExtensionException


@dataclass(frozen=True)
class HTTPException:
    id: int
    request_method: Optional[public.HTTPMethod]
    path_pattern: Optional[str]


@dataclass(frozen=True)
class RepositoryException:
    id: int
    access_type: Optional[public.RepositoryAccessType]
    repository: Optional[api.repository.Repository]


@dataclass(frozen=True)
class ExtensionException:
    id: int
    access_type: Optional[public.ExtensionAccessType]
    extension: Optional[api.extension.Extension]


ExceptionType = TypeVar("ExceptionType")


@dataclass(frozen=True)
class Category(Generic[ExceptionType]):
    rule: public.RuleValue
    exceptions: Sequence[ExceptionType]


WrapperType = public.AccessControlProfile
ArgumentsType = Tuple[
    Optional[int],
    Optional[str],
    Optional[int],
    public.RuleValue,
    public.RuleValue,
    public.RuleValue,
]


class AccessControlProfile(APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.accesscontrolprofile.AccessControlProfile
    column_names = ["id", "title", "access_token", "http", "repositories", "extensions"]

    def __init__(
        self, args: ArgumentsType = (None, None, None, "allow", "allow", "allow")
    ):
        (
            self.id,
            self.title,
            self.__token_id,
            self.http_rule,
            self.repositories_rule,
            self.extensions_rule,
        ) = args

    async def getAccessToken(
        self, critic: api.critic.Critic
    ) -> Optional[api.accesstoken.AccessToken]:
        if self.__token_id is None:
            return None
        return await api.accesstoken.fetch(critic, self.__token_id)

    async def getHTTP(
        self, critic: api.critic.Critic
    ) -> public.Category[public.HTTPException]:
        async with critic.query(
            """SELECT id, request_method, path_pattern
                 FROM accesscontrol_http
                WHERE profile={profile_id}
             ORDER BY id ASC""",
            profile_id=self.id,
        ) as result:
            return Category[public.HTTPException](
                self.http_rule,
                [
                    HTTPException(exception_id, method, path_pattern)
                    async for exception_id, method, path_pattern in result
                ],
            )

    async def getRepositories(
        self, critic: api.critic.Critic
    ) -> public.Category[public.RepositoryException]:
        async with critic.query(
            """SELECT id, access_type, repository
                 FROM accesscontrol_repositories
                WHERE profile={profile_id}
             ORDER BY id ASC""",
            profile_id=self.id,
        ) as result:
            return Category[public.RepositoryException](
                self.repositories_rule,
                [
                    RepositoryException(
                        exception_id,
                        access_type,
                        await api.repository.fetch(critic, repository_id)
                        if repository_id is not None
                        else None,
                    )
                    async for exception_id, access_type, repository_id in result
                ],
            )

    async def getExtensions(
        self, critic: api.critic.Critic
    ) -> public.Category[public.ExtensionException]:
        if not api.critic.settings().extensions.enabled:
            return Category(self.extensions_rule, [])
        async with critic.query(
            """SELECT id, access_type, extension_key
                 FROM accesscontrol_extensions
                WHERE profile={profile_id}
             ORDER BY id ASC""",
            profile_id=self.id,
        ) as result:
            return Category[public.ExtensionException](
                self.extensions_rule,
                [
                    ExtensionException(
                        exception_id,
                        access_type,
                        await api.extension.fetch(critic, key=extension_key)
                        if extension_key is not None
                        else None,
                    )
                    async for exception_id, access_type, extension_key in result
                ],
            )


@AccessControlProfile.cached
async def fetch(critic: api.critic.Critic, profile_id: Optional[int]) -> WrapperType:
    if profile_id is not None:
        async with AccessControlProfile.query(
            critic, ["id={profile_id}"], profile_id=profile_id
        ) as result:
            return await AccessControlProfile.makeOne(critic, result)

    if critic.session_type in ("system", "testing"):
        # For system (and unit testing) access, return a profile that allows
        # everything.
        return AccessControlProfile().wrap(critic)

    if critic.actual_user is not None:
        async with AccessControlProfile.query(
            critic,
            f"""SELECT {AccessControlProfile.columns()}
                  FROM {AccessControlProfile.table()}
                  JOIN useraccesscontrolprofiles AS uacp ON (
                         uacp.profile={AccessControlProfile.table()}.id
                       )
                 WHERE access_type='user'
                   AND uid={{user}}""",
            user=critic.actual_user,
        ) as result:
            try:
                return await AccessControlProfile.makeOne(critic, result)
            except result.ZeroRowsInResult:
                pass

    if critic.authentication_labels:
        labels = "|".join(sorted(critic.authentication_labels))
        async with AccessControlProfile.query(
            critic,
            f"""SELECT {AccessControlProfile.columns()}
                  FROM {AccessControlProfile.table()}
                  JOIN labeledaccesscontrolprofiles AS lacp ON (
                         lacp.profile={AccessControlProfile.table()}.id
                       )
                 WHERE labels={{labels}}""",
            labels=labels,
        ) as result:
            try:
                return await AccessControlProfile.makeOne(critic, result)
            except result.ZeroRowsInResult:
                pass

    async with AccessControlProfile.query(
        critic,
        f"""SELECT {AccessControlProfile.columns()}
              FROM {AccessControlProfile.table()}
              JOIN useraccesscontrolprofiles AS uacp ON (
                     uacp.profile={AccessControlProfile.table()}.id
                   )
             WHERE access_type='user'
               AND uid IS NULL""",
    ) as result:
        try:
            return await AccessControlProfile.makeOne(critic, result)
        except result.ZeroRowsInResult:
            pass

    # Default to an access control profile that allows everything.
    return AccessControlProfile().wrap(critic)


async def fetchAll(
    critic: api.critic.Critic, title: Optional[str]
) -> Sequence[WrapperType]:
    conditions = ["access_token IS NULL"]
    if title is not None:
        conditions.append("title={title}")

    async with AccessControlProfile.query(critic, conditions, title=title) as result:
        return await AccessControlProfile.make(critic, result)
