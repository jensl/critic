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

from typing import Callable, Collection, Tuple, Optional, Sequence

from critic.api import useremail as public
from .queryhelper import QueryHelper, QueryResult, join, left_outer_join
from .apiobject import APIObjectImplWithId
from ... import api

PublicType = public.UserEmail
ArgumentsType = Tuple[int, int, str, public.Status]


class UserEmail(PublicType, APIObjectImplWithId, module=public):
    __is_selected: Optional[bool]

    def update(self, args: ArgumentsType) -> int:
        (self.__id, self.__user_id, self.__address, self.__status) = args
        self.__is_selected = None
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def user(self) -> api.user.User:
        return await api.user.fetch(self.critic, self.__user_id)

    @property
    def address(self) -> str:
        return self.__address

    @property
    def status(self) -> public.Status:
        return self.__status

    @property
    async def is_selected(self) -> bool:
        if self.__is_selected is None:
            async with api.critic.Query[bool](
                self.critic,
                """SELECT TRUE
                     FROM selecteduseremails
                    WHERE uid={user_id}
                      AND email={useremail_id}""",
                user_id=self.__user_id,
                useremail_id=self.id,
            ) as result:
                self.__is_selected = await result.scalar(default=False)
        return self.__is_selected

    @classmethod
    def refresh_tables(cls) -> Collection[str]:
        return {UserEmail.getTableName(), "selecteduseremails"}

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "uid", "email", "status"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    useremail_id: Optional[int],
    user: Optional[api.user.User],
) -> Optional[PublicType]:
    if useremail_id is None:
        async with api.critic.Query[int](
            critic,
            """SELECT email
                 FROM selecteduseremails
                WHERE uid={user}""",
            user=user,
        ) as selected_result:
            try:
                useremail_id = await selected_result.scalar()
            except selected_result.ZeroRowsInResult:
                return None
    useremail = await UserEmail.ensureOne(
        useremail_id, queries.idFetcher(critic, UserEmail)
    )
    api.PermissionDenied.raiseUnlessUser(critic, await useremail.user)
    return useremail


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    user: Optional[api.user.User],
    status: Optional[public.Status],
    selected: Optional[bool],
) -> Sequence[PublicType]:
    if user is not None:
        api.PermissionDenied.raiseUnlessUser(critic, user)
    else:
        # We do not let users inspect each other's email addresses aside from
        # the selected one.
        api.PermissionDenied.raiseUnlessSystem(critic)
    joins = []
    conditions = []
    if user is not None:
        conditions.append("uid={user}")
    if status is not None:
        conditions.append("status={status}")
    if selected is not None:
        if selected:
            joins.append(
                join(selecteduseremails=["selecteduseremails.email=useremails.id"])
            )
        else:
            joins.append(
                left_outer_join(
                    selecteduseremails=["selecteduseremails.email=useremails.id"]
                )
            )
            conditions.append("selecteduseremails.email IS NULL")
    return UserEmail.store(
        await queries.query(
            critic,
            queries.formatQuery(*conditions, joins=joins),
            user=user,
            status=status,
        ).make(UserEmail)
    )
