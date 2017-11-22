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

from critic import api
from critic import auth


class Internal(auth.Database):
    name = "internal"

    def getFields(self):
        return [(False, "username", "Username"), (True, "password", "Password")]

    async def authenticate(self, critic, values):
        username = values["username"].strip()
        if not username:
            raise auth.InvalidUsername("Empty username", field_name="username")
        password = values["password"]
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

    async def performHTTPAuthentication(self, critic, *, username, password, token):
        if username is None or password is None:
            raise auth.AuthenticationError("Token authentication not supported")
        return await self.authenticate(
            critic, {"username": username, "password": password}
        )

    def supportsPasswordChange(self):
        return True

    async def changePassword(self, critic, modifier, current_pw, new_pw):
        async with critic.query(
            """SELECT password
                 FROM users
                WHERE id={user}""",
            user=modifier.user,
        ) as result:
            current_hashed_pw = await result.scalar()

        if current_hashed_pw is not None:
            if current_pw is None:
                api.PermissionDenied.raiseUnlessAdministrator(critic)
            else:
                await auth.checkPassword(critic, modifier.user.name, current_pw)

        new_hashed_pw = await auth.hashPassword(critic, new_pw)

        modifier.setPassword(hashed_password=new_hashed_pw)
