from dataclasses import dataclass
from typing import (
    Any,
    AsyncContextManager,
    Awaitable,
    Callable,
    Collection,
    Literal,
    NewType,
    Optional,
    Protocol,
    Tuple,
    Union,
)

from critic import api

ChannelName = NewType("ChannelName", str)
Payload = NewType("Payload", object)
RequestId = NewType("RequestId", str)
ReservationId = NewType("ReservationId", int)


class Error(Exception):
    pass


class RequestError(Error):
    pass


@dataclass(frozen=True)
class Message:
    payload: Payload


@dataclass(frozen=True)
class ReservedMessage(Message):
    notify_delivery: Callable[[], Awaitable[None]]


class MessageCallback(Protocol):
    async def __call__(self, channel_name: ChannelName, message: Message, /) -> None:
        ...


class PromiscuousCallback(Protocol):
    async def __call__(
        self, channel_names: Tuple[ChannelName, ...], message: Message, /
    ) -> None:
        ...


class IncomingRequest(Protocol):
    @property
    def request_id(self) -> RequestId:
        ...

    @property
    def payload(self) -> Payload:
        ...

    def notify_delivery(self) -> Awaitable[None]:
        ...

    def notify_response(self, value: Any) -> Awaitable[None]:
        ...

    def notify_error(self, message: str) -> Awaitable[None]:
        ...


class OutgoingRequest(Protocol):
    @property
    def delivery(self) -> Awaitable[None]:
        ...

    @property
    def response(self) -> Awaitable[object]:
        ...


class RequestCallback(Protocol):
    async def __call__(
        self, channel_name: ChannelName, request: IncomingRequest, /
    ) -> None:
        ...


class Subscription(Protocol):
    @property
    def channel_name(self) -> ChannelName:
        ...

    @property
    def reservation_id(self) -> Optional[ReservationId]:
        ...

    @property
    def message_callback(self) -> Optional[MessageCallback]:
        ...

    @property
    def request_callback(self) -> Optional[RequestCallback]:
        ...

    def unsubscribe(self) -> None:
        ...


class PublishMessage:
    channel_names: Collection[ChannelName]
    payload: Payload

    def __init__(
        self,
        channel_names: Union[ChannelName, Collection[ChannelName]],
        payload: Payload,
    ):
        self.channel_names = (
            (ChannelName(channel_names),)
            if isinstance(channel_names, str)
            else channel_names
        )
        self.payload = payload


from .client import Client


def connect(
    client_name: str,
    *,
    disconnected: Callable[[], None] = None,
    persistent: bool = False,
    mode: Literal["immediate", "lazy"] = "immediate",
    accept_failure: bool = False,
) -> AsyncContextManager[Client]:
    from critic.background.pubsub import client

    return client.ClientImpl(
        client_name,
        disconnected=disconnected,
        persistent=persistent,
        mode=mode,
        accept_failure=accept_failure,
    )


async def publish(
    critic: api.critic.Critic, client_name: str, *messages: PublishMessage
) -> None:
    from critic.background.pubsub import client

    return await client.publish(critic, client_name, *messages)


__all__ = [
    "ChannelName",
    "Payload",
    "RequestId",
    "ReservationId",
    "Message",
    "ReservedMessage",
    "MessageCallback",
    "PromiscuousCallback",
    "IncomingRequest",
    "OutgoingRequest",
    "RequestCallback",
    "Subscription",
    "Client",
    "connect",
]
