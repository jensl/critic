import logging
import types
from typing import Any, Collection, Generic, Optional, Sequence, Tuple, TypeVar

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import pubsub
from .base import TransactionBase
from .insertandcollect import InsertAndCollect
from .protocol import PublishedMessage, CreatedAPIObject

APIObjectType = TypeVar("APIObjectType", bound=api.APIObject)


class _Publisher:
    def __init__(
        self, channels: Sequence[pubsub.ChannelName], message: PublishedMessage
    ):
        self.__channels = channels
        self.__message = message

    async def publish(
        self,
    ) -> Tuple[Sequence[pubsub.ChannelName], PublishedMessage]:
        return (self.__channels, self.__message)


class CreateAPIObject(Generic[APIObjectType]):
    api_module: Optional[types.ModuleType] = None
    resource_name: Optional[str] = None
    table_name: Optional[str] = None
    id_column: str = "id"

    def __init_subclass__(cls, api_module: Optional[types.ModuleType] = None):
        if api_module:
            cls.api_module = api_module
            cls.resource_name = getattr(api_module, "resource_name")
            cls.table_name = getattr(api_module, "table_name")
            cls.id_column = getattr(api_module, "id_column", cls.id_column)

    def __init__(
        self,
        transaction: TransactionBase,
    ) -> None:
        assert self.resource_name
        self.__transaction = transaction

    @property
    def critic(self) -> api.critic.Critic:
        return self.__transaction.critic

    async def fetch(self, item_id: Any, /) -> APIObjectType:
        assert self.api_module is not None
        return await getattr(self.api_module, "fetch")(self.critic, item_id)

    def scopes(self) -> Collection[str]:
        return ()

    async def __publish(self, value: APIObjectType) -> APIObjectType:
        assert self.resource_name
        channels = [pubsub.ChannelName(self.resource_name)]
        channels.extend(
            pubsub.ChannelName(f"{scope}/{self.resource_name}")
            for scope in self.scopes()
        )
        payload = await self.create_payload(self.resource_name, value)
        if payload:
            logger.debug("publishing created object: %r to %r", payload, channels)
            self.__transaction.publish(publisher=_Publisher(channels, payload))
        return value

    async def create_payload(
        self, resource_name: str, subject: APIObjectType, /
    ) -> CreatedAPIObject:
        return CreatedAPIObject(resource_name, subject.id)

    async def insert(self, **values: dbaccess.Parameter) -> APIObjectType:
        assert self.table_name
        return await self.__publish(
            await self.__transaction.execute(
                InsertAndCollect(
                    self.table_name, returning=self.id_column, collector=self.fetch
                ).values(**values)
            )
        )
