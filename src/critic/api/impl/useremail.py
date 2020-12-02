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

from typing import Tuple, Optional, Set, Sequence

from critic.api import useremail as public
from . import apiobject
from ... import api

WrapperType = api.useremail.UserEmail
ArgumentsType = Tuple[int, int, str, api.useremail.Status, Optional[str]]


class UserEmail(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.useremail.UserEmail
    column_names = ["id", "uid", "email", "status", "token"]

    __is_selected: Optional[bool]

    def __init__(self, args: ArgumentsType) -> None:
        (self.id, self.__user_id, self.address, self.status, self.token) = args
        self.__is_selected = None

    async def getUser(self, critic: api.critic.Critic) -> api.user.User:
        return await api.user.fetch(critic, self.__user_id)

    async def isSelected(self, critic: api.critic.Critic) -> bool:
        if self.__is_selected is None:
            async with api.critic.Query[bool](
                critic,
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
    def refresh_tables(cls) -> Set[str]:
        return {UserEmail.table(), "selecteduseremails"}


@public.fetchImpl
@UserEmail.cached
async def fetch(
    critic: api.critic.Critic,
    useremail_id: Optional[int],
    user: Optional[api.user.User],
) -> Optional[WrapperType]:
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
    async with UserEmail.query(
        critic, ["id={useremail_id}"], useremail_id=useremail_id
    ) as result:
        useremail = await UserEmail.makeOne(critic, result)
    api.PermissionDenied.raiseUnlessUser(critic, await useremail.user)
    return useremail


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    user: Optional[api.user.User],
    status: Optional[api.useremail.Status],
    selected: Optional[bool],
) -> Sequence[WrapperType]:
    conditions = []
    if user is not None:
        conditions.append("useremails.uid={user}")
        api.PermissionDenied.raiseUnlessUser(critic, user)
    else:
        # We do not let users inspect each other's email addresses aside from
        # the selected one.
        api.PermissionDenied.raiseUnlessSystem(critic)
    if status is not None:
        conditions.append("useremails.status={status}")
    if selected is not None:
        conditions.append("useremails.selected={selected}")
    async with UserEmail.query(
        critic, conditions, user=user, status=status, selected=selected
    ) as result:
        return await UserEmail.make(critic, result)
