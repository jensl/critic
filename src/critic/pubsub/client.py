from __future__ import annotations

from types import TracebackType
from typing import Awaitable, Optional, Protocol, Type, overload

from critic import dbaccess

from . import (
    ChannelName,
    PublishMessage,
    ReservationId,
    MessageCallback,
    Payload,
    OutgoingRequest,
    PromiscuousCallback,
    RequestCallback,
    Subscription,
)


class Client(Protocol):
    @property
    def ready(self) -> Awaitable[None]:
        ...

    @property
    def closed(self) -> Awaitable[None]:
        ...

    async def publish(
        self, cursor: dbaccess.TransactionCursor, message: PublishMessage
    ) -> Awaitable[None]:
        ...

    async def request(
        self, payload: Payload, channel_name: ChannelName
    ) -> OutgoingRequest:
        ...

    async def subscribe(
        self,
        channel_name: ChannelName,
        callback: MessageCallback,
        /,
        *,
        reservation_id: Optional[ReservationId] = None,
    ) -> Subscription:
        ...

    async def subscribe_promiscuous(self, callback: PromiscuousCallback) -> None:
        ...

    @overload
    async def unsubscribe(self, *, channel_name: ChannelName) -> None:
        ...

    @overload
    async def unsubscribe(self, *, subscription: Subscription) -> None:
        ...

    async def unsubscribe(
        self, *, channel_name: Optional[ChannelName] = None, subscription: Optional[Subscription] = None
    ) -> None:
        ...

    async def handle_requests(
        self, channel_name: ChannelName, callback: RequestCallback
    ) -> Subscription:
        ...

    def __aenter__(self) -> Awaitable[Client]:
        ...

    def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Awaitable[Optional[bool]]:
        ...
