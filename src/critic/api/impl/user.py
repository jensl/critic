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
from collections import defaultdict
from typing import (
    Callable,
    Collection,
    Iterable,
    Optional,
    Set,
    Mapping,
    List,
    DefaultDict,
    Tuple,
    FrozenSet,
    Sequence,
    cast,
)


logger = logging.getLogger(__name__)

from critic import api
from critic.api import user as public
from .apiobject import APIObjectImplWithId
from .objectcache import ObjectCache
from .queryhelper import QueryHelper, QueryResult


async def _loadRoles(critic: api.critic.Critic, users: Iterable[User]) -> None:
    roles: DefaultDict[int, Set[str]] = defaultdict(set)

    async with api.critic.Query[Tuple[int, str]](
        critic,
        """SELECT uid, role
             FROM userroles
            WHERE uid=ANY({user_ids})""",
        user_ids=[user.id for user in users if user.id is not None],
    ) as result:
        async for user_id, role in result:
            roles[user_id].add(role)
    for user in users:
        user.setRoles(roles[int(user)])


PublicType = public.User
ArgumentsType = Tuple[
    int,
    Optional[str],
    Optional[str],
    Optional[api.user.Status],
    Optional[str],
]


class Key:
    pass


AnonymousId = -1
AnonymousKey = Key()
SystemId = -2
SystemKey = Key()


class User(PublicType, APIObjectImplWithId, module=public):
    __type: api.user.Type
    __roles: Optional[FrozenSet[str]]
    __password_status: api.user.PasswordStatus

    def __adapt__(self) -> Optional[int]:
        return None if self.__id < 0 else self.__id

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__name,
            self.__fullname,
            self.__status,
            hashed_password,
        ) = args

        self.__type = "regular"
        self.__roles = frozenset() if self.id is None else None

        if hashed_password:
            self.__password_status = "set"
        elif (
            self.__status == "current"
            and api.critic.settings().authentication.used_database == "internal"
        ):
            self.__password_status = "not-set"
        else:
            self.__password_status = "disabled"
        return self.__id

    def setType(self, new_type: api.user.Type) -> User:
        self.__type = new_type
        return self

    @property
    def type(self) -> api.user.Type:
        return self.__type

    @property
    def id(self) -> int:
        return self.__id

    @property
    def name(self) -> Optional[str]:
        return self.__name

    @property
    def fullname(self) -> Optional[str]:
        return self.__fullname

    @property
    def status(self) -> api.user.Status:
        if self.__type == "anonymous":
            return "anonymous"
        elif self.__type == "system":
            return "system"
        assert self.__status is not None
        return self.__status

    @property
    def password_status(self) -> api.user.PasswordStatus:
        return self.__password_status

    def __repr__(self) -> str:
        if self.is_regular:
            return f"User({self.id}, {self.name!r}, roles={self.roles!r})"
        elif self.is_anonymous:
            return "User(anonymous)"
        else:
            return "User(system)"

    def setRoles(self, roles: Set[str]) -> None:
        assert self.__roles is None or self.__roles == roles
        self.__roles = frozenset(roles)

    @property
    async def git_emails(self) -> Set[str]:
        async with api.critic.Query[str](
            self.critic,
            """SELECT email
                 FROM usergitemails
                WHERE uid={user_id}""",
            user_id=self.id,
        ) as result:
            return set(await result.scalars())

    @property
    async def repository_filters(
        self,
    ) -> Mapping[
        api.repository.Repository, Sequence[api.repositoryfilter.RepositoryFilter]
    ]:
        filters: DefaultDict[
            api.repository.Repository, List[api.repositoryfilter.RepositoryFilter]
        ] = defaultdict(list)

        for repository_filter in await api.repositoryfilter.fetchAll(
            self.critic, subject=self
        ):
            filters[await repository_filter.repository].append(repository_filter)

        return filters

    @property
    def roles(self) -> Collection[str]:
        assert self.__roles is not None
        return self.__roles

    def hasRole(self, role: str) -> bool:
        assert self.__roles is not None
        return role in self.__roles

    @property
    async def url_prefixes(self) -> Sequence[str]:
        url_types, _ = await api.usersetting.get(
            self.critic, "system", "urlTypes", default="main"
        )

        async with api.critic.Query[Tuple[str, str, str, str]](
            self.critic,
            """SELECT key, anonymous_scheme, authenticated_scheme, hostname
                 FROM systemidentities""",
        ) as result:
            system_identities = {
                key: (anonymous_scheme, authenticated_scheme, hostname)
                async for (
                    key,
                    anonymous_scheme,
                    authenticated_scheme,
                    hostname,
                ) in result
            }

        url_prefixes = []

        for url_type in url_types.split(","):
            if url_type in system_identities:
                (anonymous_scheme, authenticated_scheme, hostname) = system_identities[
                    url_type
                ]
                if self.type == "anonymous":
                    scheme = anonymous_scheme
                else:
                    scheme = authenticated_scheme
                url_prefixes.append("%s://%s" % (scheme, hostname))

        return url_prefixes

    @classmethod
    def refresh_tables(cls) -> Set[str]:
        return {"users", "userroles"}

    @classmethod
    async def doRefreshAll(
        cls,
        critic: api.critic.Critic,
        users: Collection[object],
        /,
    ) -> None:
        await super().doRefreshAll(critic, users)
        await _loadRoles(critic, set(cast(Iterable[User], users)))

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds

    def getCacheKeys(self) -> Collection[object]:
        if self.__type == "anonymous":
            return (AnonymousKey,)
        elif self.__type == "system":
            return (SystemKey,)
        return (self.id, self.name)


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "name", "fullname", "status", "password"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic, user_id: Optional[int], name: Optional[str]
) -> User:
    if user_id is not None:
        user = await User.ensureOne(
            user_id,
            queries.idFetcher(critic, User),
            api.user.InvalidId,
        )
    else:
        assert name is not None
        user = await User.ensureOne(
            name,
            queries.itemFetcher(critic, User, "name"),
            api.user.InvalidName,
        )
    await _loadRoles(critic, [user])
    return user


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic,
    user_ids: Optional[Sequence[int]],
    names: Optional[Sequence[str]],
) -> Sequence[User]:
    if user_ids is not None:
        users = await User.ensure(
            user_ids, queries.idsFetcher(critic, User), api.user.InvalidIds
        )
    else:
        assert names is not None
        users = await User.ensure(
            names, queries.itemsFetcher(critic, User, "name"), api.user.InvalidNames
        )

    await _loadRoles(critic, users)
    return users


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, statuses: Optional[Iterable[api.user.Status]]
) -> Sequence[User]:
    conditions = []
    if statuses is not None:
        conditions.append("status=ANY({statuses})")
        statuses = list(statuses)
    users, new_users = ObjectCache.get().store(
        User.getCacheCategory(),
        await queries.query(critic, *conditions, statuses=statuses).make(User),
    )
    await _loadRoles(critic, new_users)
    return users


@public.anonymousImpl
def anonymous(critic: api.critic.Critic) -> User:
    return User(critic, (AnonymousId, None, None, None, None)).setType("anonymous")


@public.systemImpl
def system(critic: api.critic.Critic) -> User:
    return User(critic, (SystemId, None, None, None, None)).setType("system")
