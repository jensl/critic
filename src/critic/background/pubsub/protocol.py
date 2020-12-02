from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, NewType, Optional, Tuple, Union

from critic.pubsub import ChannelName, Payload, RequestId, ReservationId

Token = NewType("Token", int)
MessageId = NewType("MessageId", int)


@dataclass
class ClientMessageBase:
    token: Token

    def ack(self) -> ServerAck:
        return ServerAck(self.token)


@dataclass
class ServerMessageBase:
    pass


@dataclass
class ClientHello(ClientMessageBase):
    name: str
    pid: int
    parallel_requests: int = 1


@dataclass
class ClientClose(ClientMessageBase):
    pass


@dataclass
class ServerClose(ServerMessageBase):
    pass


@dataclass(eq=True, frozen=True)
class Reservation:
    reservation_id: ReservationId
    message_id: MessageId


@dataclass
class ClientSubscribe(ClientMessageBase):
    channel: Optional[ChannelName] = None
    reservation_id: Optional[ReservationId] = None


@dataclass
class ClientUnsubscribe(ClientMessageBase):
    channel: ChannelName
    reservation_id: Optional[ReservationId] = None


@dataclass
class ClientPublish(ClientMessageBase):
    channels: Tuple[ChannelName, ...]
    payload: Payload
    reservations: List[Reservation]


@dataclass
class ServerPublish(ServerMessageBase):
    channels: Tuple[ChannelName, ...]
    payload: Payload
    reservations: List[Reservation]


@dataclass
class ClientPublishConfirmation(ClientMessageBase):
    reservation: Reservation


@dataclass
class ClientHandleRequests(ClientMessageBase):
    channel: ChannelName


@dataclass
class ClientRequest(ClientMessageBase):
    channel: ChannelName
    request_id: RequestId
    payload: Payload

    def forwarded_request(self) -> ServerRequest:
        return ServerRequest(self.channel, self.request_id, self.payload)

    def delivery(self, response: Union[Target, Error]) -> ServerRequestDelivery:
        return ServerRequestDelivery(self.request_id, response)

    def result(self, response: Union[Value, Error]) -> ServerRequestResult:
        return ServerRequestResult(self.request_id, response)


@dataclass
class ServerRequest(ServerMessageBase):
    channel: ChannelName
    request_id: RequestId
    payload: Payload

    def delivery(self, token: Token) -> ClientRequestDelivery:
        return ClientRequestDelivery(token, self.request_id)

    def result(
        self, token: Token, response: Union[Value, Error]
    ) -> ClientRequestResult:
        return ClientRequestResult(token, self.request_id, response)


@dataclass
class Value:
    value: Any


@dataclass
class Error:
    message: str


@dataclass
class ClientRequestDelivery(ClientMessageBase):
    request_id: RequestId


@dataclass
class ClientRequestResult(ClientMessageBase):
    request_id: RequestId
    response: Union[Value, Error]


@dataclass
class Target:
    name: str
    pid: Optional[int]


@dataclass
class ServerRequestDelivery(ServerMessageBase):
    request_id: RequestId
    response: Union[Target, Error]


@dataclass
class ServerRequestResult(ServerMessageBase):
    request_id: RequestId
    response: Union[Value, Error]


@dataclass
class ServerAck(ServerMessageBase):
    token: Token


ClientMessage = Union[
    ClientHello,
    ClientSubscribe,
    ClientUnsubscribe,
    ClientPublish,
    ClientPublishConfirmation,
    ClientHandleRequests,
    ClientRequest,
    ClientRequestDelivery,
    ClientRequestResult,
    ClientClose,
]

ServerMessage = Union[
    ServerPublish,
    ServerRequest,
    ServerRequestDelivery,
    ServerRequestResult,
    ServerAck,
    ServerClose,
]
