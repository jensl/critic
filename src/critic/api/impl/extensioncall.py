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

from datetime import datetime
import pickle
from typing import Callable, Optional, Sequence, Tuple, Union

from critic import api
from critic.api import extensioncall as public
from critic.protocol.extensionhost import CallRequest, CallResponse

from .apiobject import APIObjectImplWithId
from .queryhelper import Query, QueryHelper, QueryResult, join

PublicType = public.ExtensionCall
ArgumentsType = Tuple[
    int,
    int,
    Optional[int],
    Optional[int],
    bytes,
    Optional[bytes],
    Optional[bool],
    datetime,
    Optional[datetime],
]


class ExtensionCall(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__version_id,
            self.__user_id,
            self.__accesstoken_id,
            self.__request,
            self.__response,
            self.__successful,
            self.__request_time,
            self.__response_time,
        ) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def version(self) -> api.extensionversion.ExtensionVersion:
        return await api.extensionversion.fetch(self.critic, self.__version_id)

    @property
    async def user(self) -> Optional[api.user.User]:
        return (
            None
            if self.__user_id is None
            else await api.user.fetch(self.critic, self.__user_id)
        )

    @property
    async def accesstoken(self) -> Optional[api.accesstoken.AccessToken]:
        return (
            None
            if self.__accesstoken_id is None
            else await api.accesstoken.fetch(self.critic, self.__accesstoken_id)
        )

    @property
    def request(self) -> CallRequest:
        request = pickle.loads(self.__request)
        assert isinstance(request, CallRequest)
        return request

    @property
    def response(self) -> Optional[CallResponse]:
        if self.__response is None:
            return None
        response = pickle.loads(self.__response)
        assert isinstance(response, CallResponse)
        return response

    @property
    def successful(self) -> Optional[bool]:
        return self.__successful

    @property
    def request_time(self) -> datetime:
        return self.__request_time

    @property
    def response_time(self) -> Optional[datetime]:
        return self.__response_time

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "version",
    "uid",
    "accesstoken",
    "request",
    "response",
    "successful",
    "request_time",
    "response_time",
    default_order_by=[f"{PublicType.getTableName()}.request_time ASC"],
)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, call_id: int) -> PublicType:
    return await ExtensionCall.ensureOne(
        call_id, queries.idFetcher(critic, ExtensionCall)
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    version: Optional[api.extensionversion.ExtensionVersion],
    extension: Optional[api.extension.Extension],
    successful: Optional[bool],
) -> Sequence[PublicType]:
    conditions = []
    if successful is not None:
        conditions.append("successful={successful}")
    if version is not None:
        conditions.append("version={version}")
    if extension is not None:
        query = queries.formatQuery(
            "extensionversions.extension={extension}",
            *conditions,
            joins=[
                join(extensionversions=["extensionversions.id=extensioncalls.version"])
            ],
        )
    else:
        query = queries.formatQuery(*conditions)
    return ExtensionCall.store(
        await queries.query(
            critic,
            query,
            version=version,
            extension=extension,
            successful=successful,
        ).make(ExtensionCall)
    )
