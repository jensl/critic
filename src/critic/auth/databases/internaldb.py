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

from typing import Mapping, Optional, Sequence

from critic import api
from critic import auth


class Internal(auth.Database, dbname="internal"):
    def getFields(self) -> Sequence[auth.database.Field]:
        return [
            auth.database.Field(False, "username", "Username"),
            auth.database.Field(True, "password", "Password"),
        ]

    async def authenticate(
        self, critic: api.critic.Critic, fields: Mapping[str, str]
    ) -> api.user.User:
        username = fields["username"].strip()
        if not username:
            raise auth.InvalidUsername("Empty username", field_name="username")
        password = fields["password"]
        if not password:
            raise auth.WrongPassword("Empty password", field_name="password")

        try:
            user = await auth.checkPassword(critic, username, password)
        except auth.InvalidUsername as error:
            raise auth.InvalidUsername(str(error), field_name="username")
        except auth.WrongPassword as error:
            raise auth.WrongPassword(str(error), field_name="password")
        else:
            await critic.setActualUser(user)

        return user

    async def performHTTPAuthentication(
        self,
        critic: api.critic.Critic,
        *,
        username: Optional[str],
        password: Optional[str],
        token: Optional[str]
    ) -> api.user.User:
        if username is None or password is None:
            raise auth.AuthenticationError("Token authentication not supported")
        return await self.authenticate(
            critic, {"username": username, "password": password}
        )

    def supportsPasswordChange(self) -> bool:
        return True

    async def changePassword(
        self,
        critic: api.critic.Critic,
        user: api.user.User,
        modifier: auth.database.Modifier,
        current_pw: str,
        new_pw: str,
    ) -> None:
        async with critic.query(
            """SELECT password
                 FROM users
                WHERE id={user}""",
            user=critic.actual_user,
        ) as result:
            current_hashed_pw = await result.scalar()

        if current_hashed_pw is not None:
            username = user.name
            assert username

            if current_pw is None:
                api.PermissionDenied.raiseUnlessAdministrator(critic)
            else:
                await auth.checkPassword(critic, username, current_pw)

        new_hashed_pw = await auth.hashPassword(critic, new_pw)

        await modifier.setPassword(hashed_password=new_hashed_pw)
