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

import sshpubkeys
from typing import Tuple, Optional, Sequence

from . import apiobject
from critic import api


WrapperType = api.usersshkey.UserSSHKey
ArgumentsType = Tuple[int, int, str, str, str]


class UserSSHKey(apiobject.APIObject):
    wrapper_class = api.usersshkey.UserSSHKey
    column_names = ["id", "uid", "type", "key", "comment"]

    __parsed_key: Optional[sshpubkeys.SSHKey]

    def __init__(self, args: ArgumentsType) -> None:
        (self.id, self.__user_id, self.type, self.key, self.comment) = args
        self.__parsed_key = None

    async def getUser(self, critic: api.critic.Critic) -> api.user.User:
        return await api.user.fetch(critic, self.__user_id)

    def __parsedKey(self) -> sshpubkeys.SSHKey:
        if self.__parsed_key is None:
            self.__parsed_key = sshpubkeys.SSHKey(f"{self.type} {self.key}")
        return self.__parsed_key

    def getBits(self) -> int:
        return self.__parsedKey().bits

    def getFingerprint(self) -> str:
        return self.__parsedKey().hash_md5().replace("MD5:", "")


@UserSSHKey.cached
async def fetch(
    critic: api.critic.Critic,
    usersshkey_id: Optional[int],
    key_type: Optional[str],
    key: Optional[str],
) -> Optional[WrapperType]:
    if usersshkey_id is not None:
        condition = "id={usersshkey_id}"
    else:
        condition = "type={key_type} AND key={key}"
    async with UserSSHKey.query(
        critic, [condition], usersshkey_id=usersshkey_id, key_type=key_type, key=key
    ) as result:
        try:
            usersshkey = await UserSSHKey.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if usersshkey_id is not None:
                raise
            return None
    api.PermissionDenied.raiseUnlessUser(critic, await usersshkey.user)
    return usersshkey


async def fetchAll(
    critic: api.critic.Critic, user: Optional[api.user.User]
) -> Sequence[WrapperType]:
    conditions = ["TRUE"]
    if user is not None:
        api.PermissionDenied.raiseUnlessUser(critic, user)
        conditions.append("uid={user}")
    else:
        api.PermissionDenied.raiseUnlessSystem(critic)
    async with critic.query(
        f"""SELECT {UserSSHKey.columns()}
              FROM {UserSSHKey.table()}
             WHERE {" AND ".join(conditions)}""",
        user=user,
    ) as result:
        return await UserSSHKey.make(critic, result)
