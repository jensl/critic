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
from typing import Callable, Tuple, Optional, Sequence

from critic import api
from critic.api import usersshkey as public
from critic.api.impl.queryhelper import QueryHelper, QueryResult
from .apiobject import APIObjectImplWithId


PublicType = public.UserSSHKey
ArgumentsType = Tuple[int, int, str, str, str]


class UserSSHKey(PublicType, APIObjectImplWithId, module=public):
    __parsed_key: Optional[sshpubkeys.SSHKey]

    def __str__(self) -> str:
        return f"{self.type} {self.key}"

    def update(self, args: ArgumentsType) -> int:
        (self.__id, self.__user_id, self.__type, self.__key, self.__comment) = args
        self.__parsed_key = None
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def user(self) -> api.user.User:
        return await api.user.fetch(self.critic, self.__user_id)

    @property
    def type(self) -> str:
        return self.__type

    @property
    def key(self) -> str:
        return self.__key

    @property
    def comment(self) -> str:
        return self.__comment

    @property
    def bits(self) -> int:
        return self.__parsedKey().bits

    @property
    def fingerprint(self) -> str:
        return self.__parsedKey().hash_md5().replace("MD5:", "")

    def __parsedKey(self) -> sshpubkeys.SSHKey:
        if self.__parsed_key is None:
            self.__parsed_key = sshpubkeys.SSHKey(f"{self.type} {self.key}")
        return self.__parsed_key

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "uid", "type", "key", "comment"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    usersshkey_id: Optional[int],
    key_type: Optional[str],
    key: Optional[str],
) -> Optional[PublicType]:
    if usersshkey_id is not None:
        usersshkey = await UserSSHKey.ensureOne(
            usersshkey_id, queries.idFetcher(critic, UserSSHKey)
        )
    else:
        usersshkey = UserSSHKey.storeOne(
            await queries.query(critic, type=key_type, key=key).makeOne(UserSSHKey)
        )
        if not usersshkey:
            return None
    api.PermissionDenied.raiseUnlessUser(critic, await usersshkey.user)
    return usersshkey


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, user: Optional[api.user.User]
) -> Sequence[PublicType]:
    conditions = []
    if user is not None:
        api.PermissionDenied.raiseUnlessUser(critic, user)
        conditions.append("uid={user}")
    else:
        api.PermissionDenied.raiseUnlessSystem(critic)
    return UserSSHKey.store(
        await queries.query(critic, *conditions, user=user).make(UserSSHKey)
    )
