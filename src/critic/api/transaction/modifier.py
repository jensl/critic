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

from __future__ import annotations
import contextlib

from typing import (
    AsyncIterator,
    Optional,
    TypeVar,
    Any,
    Dict,
    Tuple,
    Sequence,
    Generic,
)

from critic import api
from critic import pubsub

from .base import TransactionBase
from .item import Delete, Update
from .protocol import (
    ModifiedAPIObject,
    DeletedAPIObject,
    PublishedMessage,
)

APIObjectType = TypeVar("APIObjectType", bound=api.APIObject)


class ModifierBase:
    updates: Dict[str, Any]

    def __init__(
        self,
        transaction: TransactionBase,
    ) -> None:
        self.transaction = transaction
        self.updates = {}
        self.modified = False
        self.deleted = False


class Modifier(Generic[APIObjectType], ModifierBase):
    def __init__(
        self,
        transaction: TransactionBase,
        subject: APIObjectType,
    ) -> None:
        super().__init__(transaction)
        self.transaction.publish(publisher=self)
        self.subject = subject

    @property
    def critic(self) -> api.critic.Critic:
        return self.transaction.critic

    @property
    def resource_name(self) -> str:
        return self.subject.getResourceName()

    @property
    def subject_id(self) -> int:
        return self.subject.id

    async def reload(self) -> APIObjectType:
        return await self.subject.reload()

    @contextlib.asynccontextmanager
    async def update(self, **fields: Any) -> AsyncIterator[Update]:
        update = Update(self.subject)
        yield update
        await self.transaction.execute(update)
        self.modified = True
        self.updates.update(fields)

    async def delete(self) -> None:
        await self.transaction.execute(Delete(self.subject))
        self.deleted = True

    # async def fetch(self, expression: str, value_type: Type[SQLValue]) -> SQLValue:
    #     return await self.transaction.execute(Fetch[SQLValue](expression))

    # async def fetchAll(
    #     self, expression: str, value_type: Type[dbaccess.RowType]
    # ) -> Sequence[dbaccess.RowType]:
    #     return await self.transaction.execute(FetchAll[dbaccess.RowType](expression))

    async def publish(
        self,
    ) -> Optional[Tuple[Sequence[pubsub.ChannelName], PublishedMessage]]:
        resource_name = self.resource_name
        object_id = self.subject_id
        if object_id is None:
            return None

        message: PublishedMessage
        if self.deleted:
            message = await self.create_deleted_payload()
        elif self.modified or self.updates:
            message = await self.create_modified_payload()
        else:
            return None

        return (
            [pubsub.ChannelName(f"{resource_name}/{object_id}")],
            message,
        )

    async def create_modified_payload(self) -> ModifiedAPIObject:
        return ModifiedAPIObject(self.resource_name, self.subject_id, self.updates)

    async def create_deleted_payload(self) -> DeletedAPIObject:
        return DeletedAPIObject(self.resource_name, self.subject_id)
