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
    Iterable,
    Optional,
    Set,
    Mapping,
    List,
    DefaultDict,
    Tuple,
    FrozenSet,
    Any,
    Sequence,
    Dict,
    Type,
    Union,
)

logger = logging.getLogger(__name__)

from . import apiobject
from critic import api


async def _loadRoles(critic: api.critic.Critic, users: Iterable[api.user.User]) -> None:
    roles: DefaultDict[int, Set[str]] = defaultdict(set)

    async with api.critic.Query[Tuple[int, str]](
        critic,
        """SELECT uid, role
             FROM userroles
            WHERE {uid=user_ids:array}""",
        user_ids=[user.id for user in users if user.id is not None],
    ) as result:
        async for user_id, role in result:
            roles[user_id].add(role)
    for user in users:
        user._impl.setRoles(roles[int(user)])


WrapperType = api.user.User
ArgumentsType = Tuple[
    Optional[int],
    Optional[str],
    Optional[str],
    Optional[api.user.Status],
    Optional[str],
]


class User(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.user.User
    column_names = ["id", "name", "fullname", "status", "password"]

    roles: Optional[FrozenSet[str]]

    def __init__(
        self,
        args: ArgumentsType = (None, None, None, None, None),
        *,
        user_type: api.user.Type = "regular",
    ) -> None:
        (self.id, self.name, self.fullname, self.status, hashed_password,) = args

        self.type = user_type
        self.roles = frozenset() if self.id is None else None

        if hashed_password:
            self.password_status = "set"
        elif (
            self.status == "current"
            and api.critic.settings().authentication.used_database == "internal"
        ):
            self.password_status = "not-set"
        else:
            self.password_status = "disabled"

    def __repr__(self) -> str:
        return "User(%r, roles=%r)" % (self.id, self.roles)

    def setRoles(self, roles: Set[str]) -> None:
        assert self.roles is None or self.roles == roles
        self.roles = frozenset(roles)

    async def getGitEmails(self, critic: api.critic.Critic) -> Set[str]:
        async with api.critic.Query[str](
            critic,
            """SELECT email
                 FROM usergitemails
                WHERE uid={user_id}""",
            user_id=self.id,
        ) as result:
            return set(await result.scalars())

    async def getRepositoryFilters(
        self, critic: api.critic.Critic
    ) -> Mapping[
        api.repository.Repository, List[api.repositoryfilter.RepositoryFilter]
    ]:
        from .repositoryfilter import RepositoryFilter

        filters: DefaultDict[
            api.repository.Repository, List[api.repositoryfilter.RepositoryFilter]
        ] = defaultdict(list)

        async with RepositoryFilter.query(
            critic, ["uid={user_id}"], user_id=self.id
        ) as result:
            for repository_filter in await RepositoryFilter.make(critic, result):
                filters[await repository_filter.repository].append(repository_filter)

        return filters

    def hasRole(self, role: str) -> bool:
        assert self.roles is not None
        return role in self.roles

    # async def getPreference(
    #     self,
    #     wrapper: WrapperType,
    #     item: str,
    #     repository: Optional[api.repository.Repository],
    # ):
    #     critic = wrapper.critic
    #     async with api.critic.Query[str](
    #         critic,
    #         """SELECT type
    #              FROM preferences
    #             WHERE item={item}""",
    #         item=item,
    #     ) as result:
    #         try:
    #             preference_type = await result.scalar()
    #         except result.ZeroRowsInResult:
    #             raise api.preference.InvalidPreferenceItem(item)

    #     arguments = {"item": item}
    #     conditions = ["item={item}"]

    #     if preference_type in ("boolean", "integer"):
    #         column = "integer"
    #     else:
    #         column = "string"

    #     if self.type == "regular":
    #         arguments["user_id"] = self.id
    #         conditions.append("(uid={user_id} OR uid IS NULL)")
    #     else:
    #         conditions.append("uid IS NULL")

    #     if repository is not None:
    #         arguments["repository_id"] = repository.id
    #         conditions.append("(repository={repository_id} OR repository IS NULL)")
    #     else:
    #         conditions.append("repository IS NULL")

    #     async with critic.query(
    #         f"""SELECT {column},
    #                    COALESCE(uid, -1),
    #                    COALESCE(repository, -1)
    #               FROM userpreferences
    #              WHERE {" AND ".join(conditions)}""",
    #         **arguments,
    #     ) as result:
    #         rows = await result.all()

    #     row = sorted(rows, key=lambda row: row[1:])[-1]
    #     value, user_id, repository_id = row

    #     if preference_type == "boolean":
    #         value = bool(value)

    #     if user_id == -1:
    #         wrapper = None
    #     if repository_id == -1:
    #         repository = None

    #     return api.preference.Preference(item, value, wrapper, repository)

    async def getURLPrefixes(self, wrapper: WrapperType) -> Sequence[str]:
        url_types, _ = await api.usersetting.get(
            wrapper.critic, "system", "urlTypes", default="main"
        )

        async with api.critic.Query[Tuple[str, str, str, str]](
            wrapper.critic,
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

    @staticmethod
    def refresh_tables() -> Set[str]:
        return {"users", "userroles"}

    @classmethod
    async def refresh(
        cls: Type[User],
        critic: api.critic.Critic,
        tables: Set[str],
        cached_users: Mapping[Any, WrapperType],
    ) -> None:
        await super().refresh(critic, tables, cached_users)
        await _loadRoles(critic, cached_users.values())


@User.cached
async def fetch(
    critic: api.critic.Critic, user_id: Optional[int], name: Optional[str]
) -> WrapperType:
    try:
        user_ids = None if user_id is None else [user_id]
        names = None if name is None else [name]
        users = await fetchMany(critic, user_ids, names)
    except api.user.InvalidIds as error:
        raise api.user.InvalidId(invalid_id=error.values[0]) from None
    except api.user.InvalidNames as error:
        raise api.user.InvalidName(value=error.values[0]) from None
    return users[0]


@User.cachedMany
async def fetchMany(
    critic: api.critic.Critic,
    user_ids_iterable: Optional[Iterable[int]],
    names_iterable: Optional[Iterable[str]] = None,
) -> Sequence[WrapperType]:
    user_ids: Optional[List[int]] = None
    names: Optional[List[str]] = None

    if user_ids_iterable is not None:
        user_ids = list(user_ids_iterable)
        condition = "users.id=ANY({user_ids})"
    else:
        assert names_iterable is not None
        names = list(names_iterable)
        condition = "users.name=ANY({names})"

    async with User.query(
        critic, [condition], user_ids=user_ids, names=names
    ) as result:
        rows = await result.all()

    row_lookup: Dict[Optional[Union[int, str]], ArgumentsType]

    if user_ids is not None:
        row_lookup = dict((row[0], row) for row in rows)
        if len(rows) < len(user_ids):
            raise api.user.InvalidIds(
                invalid_ids=[
                    user_id for user_id in user_ids if user_id not in row_lookup
                ]
            )
        users = await User.make(critic, (row_lookup[key] for key in user_ids))
    else:
        assert names is not None
        row_lookup = dict((row[1], row) for row in rows)
        if len(rows) < len(names):
            raise api.user.InvalidNames(
                values=[name for name in names if name not in row_lookup]
            )
        users = await User.make(critic, (row_lookup[key] for key in names))

    await _loadRoles(critic, users)
    return users


async def fetchAll(
    critic: api.critic.Critic, statuses: Optional[Iterable[api.user.Status]]
) -> Sequence[WrapperType]:
    conditions = ["TRUE"]
    if statuses is not None:
        conditions.append("{status=statuses:array}")
        statuses = list(statuses)
    async with User.query(critic, conditions, statuses=statuses) as result:
        users = await User.make(critic, result)
    await _loadRoles(critic, users)
    return users


def anonymous(critic: api.critic.Critic) -> WrapperType:
    return User(user_type="anonymous").wrap(critic)


def system(critic: api.critic.Critic) -> WrapperType:
    return User(user_type="system").wrap(critic)
