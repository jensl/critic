# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2021 the Critic contributors, Opera Software ASA
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

from abc import abstractmethod
from datetime import datetime
from typing import Awaitable, Callable, Optional, Sequence, Union, overload

from critic import api
from critic.api.apiobject import FunctionRef
from critic.protocol.extensionhost import CallRequest, CallResponse


class Error(api.APIError, object_type="extension call"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid extension call id is used."""

    pass


def id_from_string(value: str) -> int:
    return int.from_bytes(bytes.fromhex(value), "big", signed=True)


def id_to_string(value: int) -> str:
    return value.to_bytes(8, "big", signed=True).hex()


class ExtensionCall(api.APIObjectWithId):
    @property
    @abstractmethod
    def id(self) -> int:
        ...

    @property
    def id_string(self) -> str:
        return id_to_string(self.id)

    @property
    @abstractmethod
    async def version(self) -> api.extensionversion.ExtensionVersion:
        ...

    @property
    async def extension(self) -> api.extension.Extension:
        return await (await self.version).extension

    @property
    @abstractmethod
    async def user(self) -> Optional[api.user.User]:
        ...

    @property
    @abstractmethod
    async def accesstoken(self) -> Optional[api.accesstoken.AccessToken]:
        ...

    @property
    @abstractmethod
    def request(self) -> CallRequest:
        ...

    @property
    @abstractmethod
    def response(self) -> Optional[CallResponse]:
        ...

    @property
    @abstractmethod
    def successful(self) -> Optional[bool]:
        ...

    @property
    @abstractmethod
    def request_time(self) -> datetime:
        ...

    @property
    @abstractmethod
    def response_time(self) -> Optional[datetime]:
        ...


async def fetch(
    critic: api.critic.Critic, call_id: Union[int, str], /
) -> ExtensionCall:
    if isinstance(call_id, str):
        call_id = id_from_string(call_id)
    return await fetchImpl.get()(critic, call_id)


@overload
async def fetchAll(
    critic: api.critic.Critic,
    *,
    version: Optional[api.extensionversion.ExtensionVersion] = None,
    successful: Optional[bool] = None,
) -> Sequence[ExtensionCall]:
    ...


@overload
async def fetchAll(
    critic: api.critic.Critic,
    *,
    extension: Optional[api.extension.Extension] = None,
    successful: Optional[bool] = None,
) -> Sequence[ExtensionCall]:
    ...


async def fetchAll(
    critic: api.critic.Critic,
    *,
    version: Optional[api.extensionversion.ExtensionVersion] = None,
    extension: Optional[api.extension.Extension] = None,
    successful: Optional[bool] = None,
) -> Sequence[ExtensionCall]:
    return await fetchAllImpl.get()(critic, version, extension, successful)


resource_name = table_name = "extensioncalls"

fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, int], Awaitable[ExtensionCall]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.extensionversion.ExtensionVersion],
            Optional[api.extension.Extension],
            Optional[bool],
        ],
        Awaitable[Sequence[ExtensionCall]],
    ]
] = FunctionRef()
