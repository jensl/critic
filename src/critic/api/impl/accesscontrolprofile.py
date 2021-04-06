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

from typing import Callable, Optional, Tuple, Generic, Sequence

from critic import api, dbaccess
from critic.api import accesscontrolprofile as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult, join


class Category(Generic[public.ExceptionType]):
    __rule: public.RuleValue
    _exceptions: Sequence[public.ExceptionType]

    def __init__(
        self, rule: public.RuleValue, exceptions: Sequence[public.ExceptionType]
    ):
        self.__rule = rule
        self._exceptions = exceptions

    @property
    def rule(self) -> public.RuleValue:
        return self.__rule

    # @property
    # def exceptions(self) -> Sequence[public.ExceptionType]:
    #     return self.__exceptions


class HTTPCategory:
    def __init__(
        self, rule: public.RuleValue, exceptions: Sequence[public.HTTPException]
    ):
        self.__rule = rule
        self.__exceptions = exceptions

    @property
    def rule(self) -> public.RuleValue:
        return self.__rule

    @property
    def exceptions(self) -> Sequence[public.HTTPException]:
        return self.__exceptions


PublicType = public.AccessControlProfile
ArgumentsType = Tuple[
    int,
    Optional[str],
    Optional[int],
    public.RuleValue,
    public.RuleValue,
    public.RuleValue,
]

AllowEverythingId = -1
ALLOW_EVERYTHING_ARGS: ArgumentsType = (
    AllowEverythingId,
    None,
    None,
    "allow",
    "allow",
    "allow",
)


class AccessControlProfile(PublicType, APIObjectImplWithId, module=public):
    http_rule: public.RuleValue
    repositories_rule: public.RuleValue
    extensions_rule: public.RuleValue

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__title,
            self.__token_id,
            self.__http_rule,
            self.__repositories_rule,
            self.__extensions_rule,
        ) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def title(self) -> Optional[str]:
        return self.__title

    @property
    async def access_token(self) -> Optional[api.accesstoken.AccessToken]:
        if self.__token_id is None:
            return None
        return await api.accesstoken.fetch(self.critic, self.__token_id)

    @property
    async def http(self) -> public.HTTPCategory:
        async with api.critic.Query[Tuple[int, public.HTTPMethod, str]](
            self.critic,
            """SELECT id, request_method, path_pattern
                 FROM accesscontrol_http
                WHERE profile={profile_id}
             ORDER BY id ASC""",
            profile_id=self.id,
        ) as result:
            return public.HTTPCategory(
                self.__http_rule,
                [
                    public.HTTPException(exception_id, method, path_pattern)
                    async for exception_id, method, path_pattern in result
                ],
            )

    @property
    async def repositories(self) -> public.RepositoryCategory:
        async with api.critic.Query[Tuple[int, public.RepositoryAccessType, int]](
            self.critic,
            """SELECT id, access_type, repository
                 FROM accesscontrol_repositories
                WHERE profile={profile_id}
             ORDER BY id ASC""",
            profile_id=self.id,
        ) as result:
            return public.RepositoryCategory(
                self.__repositories_rule,
                [
                    public.RepositoryException(
                        exception_id,
                        access_type,
                        await api.repository.fetch(self.critic, repository_id)
                        if repository_id is not None
                        else None,
                    )
                    async for exception_id, access_type, repository_id in result
                ],
            )

    @property
    async def extensions(self) -> public.ExtensionCategory:
        if not api.critic.settings().extensions.enabled:
            return public.ExtensionCategory(self.extensions_rule, [])
        async with api.critic.Query[Tuple[int, public.ExtensionAccessType, str]](
            self.critic,
            """SELECT id, access_type, extension_key
                 FROM accesscontrol_extensions
                WHERE profile={profile_id}
             ORDER BY id ASC""",
            profile_id=self.id,
        ) as result:
            return public.ExtensionCategory(
                self.__extensions_rule,
                [
                    public.ExtensionException(
                        exception_id,
                        access_type,
                        await api.extension.fetch(self.critic, key=extension_key)
                        if extension_key is not None
                        else None,
                    )
                    async for exception_id, access_type, extension_key in result
                ],
            )

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


acps = PublicType.getTableName()

queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "title",
    "access_token",
    "http",
    "repositories",
    "extensions",
)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, profile_id: Optional[int]) -> PublicType:
    if profile_id is not None:
        return await AccessControlProfile.ensureOne(
            profile_id,
            queries.idFetcher(critic, AccessControlProfile),
            public.InvalidId,
        )

    if critic.session_type in ("system", "testing"):
        # For system (and unit testing) access, return a profile that allows
        # everything.
        return AccessControlProfile(critic, ALLOW_EVERYTHING_ARGS)

    async def attempt(
        query: QueryResult[ArgumentsType],
    ) -> AccessControlProfile:
        return AccessControlProfile.storeOne(
            await query.makeOne(
                AccessControlProfile,
            )
        )

    def by_user(
        user: Optional[api.user.User],
    ) -> QueryResult[ArgumentsType]:
        return queries.query(
            critic,
            queries.formatQuery(
                "access_type='user'",
                "uid={user}" if user is not None else "uid IS NULL",
                joins=[
                    join(
                        useraccesscontrolprofiles=[
                            f"useraccesscontrolprofiles.profile={acps}.id"
                        ],
                    )
                ],
            ),
            user=user,
        )

    if critic.actual_user is not None:
        try:
            return await attempt(by_user(critic.actual_user))
        except dbaccess.ZeroRowsInResult:
            pass

    if critic.authentication_labels:
        labels = "|".join(sorted(critic.authentication_labels))
        try:
            return await attempt(
                queries.query(
                    critic,
                    queries.formatQuery(
                        "labels={labels}",
                        joins=[
                            join(
                                labeledaccesscontrolprofiles=[
                                    f"labeledaccesscontrolprofiles.profile={acps}.id"
                                ],
                            )
                        ],
                    ),
                    labels=labels,
                )
            )
        except dbaccess.ZeroRowsInResult:
            pass

    try:
        return await attempt(by_user(None))
    except dbaccess.ZeroRowsInResult:
        pass

    # Default to an access control profile that allows everything.
    return AccessControlProfile(critic, ALLOW_EVERYTHING_ARGS)


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, title: Optional[str]
) -> Sequence[PublicType]:
    conditions = ["access_token IS NULL"]
    if title is not None:
        conditions.append("title={title}")

    return AccessControlProfile.store(
        await queries.query(critic, *conditions, title=title).make(
            AccessControlProfile
        ),
    )
