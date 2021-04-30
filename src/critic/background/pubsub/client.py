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

import asyncio
import functools
import logging
import os
import pickle
import secrets
from dataclasses import dataclass
from typing import (
    Any,
    AsyncContextManager,
    Awaitable,
    Callable,
    Dict,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic.pubsub import (
    ChannelName,
    Payload,
    PublishMessage,
    RequestId,
    ReservationId,
    Message,
    ReservedMessage,
    MessageCallback,
    PromiscuousCallback,
    IncomingRequest,
    OutgoingRequest,
    RequestCallback,
    Subscription,
    Client,
    Error,
    RequestError,
    connectImpl,
    publishImpl,
)

from . import protocol
from ..utils import ServiceError
from ..messagechannel import MessageChannel


async def invoke_message_callback(
    callback: MessageCallback,
    channel_name: ChannelName,
    message: Message,
) -> None:
    try:
        await callback(channel_name, message)
    except Exception:
        logger.exception("Pub/Sub message callback crashed")


async def invoke_promiscuous_callback(
    callback: PromiscuousCallback,
    channel_names: Tuple[ChannelName, ...],
    message: Message,
) -> None:
    try:
        await callback(channel_names, message)
    except Exception:
        logger.exception("Pub/Sub promiscuous callback crashed")


async def invoke_request_callback(
    callback: RequestCallback,
    channel_name: ChannelName,
    request: IncomingRequest,
) -> None:
    try:
        await callback(channel_name, request)
    except Exception:
        logger.exception("Pub/Sub request callback crashed")


@dataclass
class SubscriptionImpl:
    client: ClientImpl
    __channel_name: ChannelName
    __message_callback: Optional[MessageCallback] = None
    __request_callback: Optional[RequestCallback] = None
    __reservation_id: Optional[ReservationId] = None

    def __hash__(self) -> int:
        return hash(id(self))

    def __eq__(self, other: object) -> bool:
        return id(self) == id(other)

    @property
    def channel_name(self) -> ChannelName:
        return self.__channel_name

    @property
    def reservation_id(self) -> Optional[ReservationId]:
        return self.__reservation_id

    @property
    def message_callback(self) -> Optional[MessageCallback]:
        return self.__message_callback

    @property
    def request_callback(self) -> Optional[RequestCallback]:
        return self.__request_callback

    async def unsubscribe(self) -> None:
        await self.client.unsubscribe(subscription=self)


class OutgoingRequestImpl:
    __delivery: "asyncio.Future[None]"
    __response: "asyncio.Future[object]"

    def __init__(self) -> None:
        loop = asyncio.get_running_loop()
        self.__delivery = loop.create_future()
        self.__response = loop.create_future()

    @property
    def delivery(self) -> "asyncio.Future[None]":
        return self.__delivery

    @property
    def response(self) -> "asyncio.Future[object]":
        return self.__response


class RequestNotifyResponse(Protocol):
    async def __call__(
        self, *, value: Optional[Any] = None, message: Optional[str] = None
    ) -> None:
        ...


class IncomingRequestImpl:
    def __init__(
        self,
        notify_delivery: Callable[[], Awaitable[None]],
        notify_response: RequestNotifyResponse,
        request_id: RequestId,
        payload: Payload,
    ):
        self.__notify_delivery = notify_delivery
        self.__notify_response = notify_response
        self.__request_id = request_id
        self.__payload = payload

    @property
    def request_id(self) -> RequestId:
        return self.__request_id

    @property
    def payload(self) -> Payload:
        return self.__payload

    async def notify_delivery(self) -> None:
        await self.__notify_delivery()

    async def notify_response(self, value: Any) -> None:
        await self.__notify_response(value=value)

    async def notify_error(self, message: str) -> None:
        await self.__notify_response(message=message)


class ClientImpl:
    __connection: Optional[
        MessageChannel[protocol.ClientMessage, protocol.ServerMessage]
    ]
    __futures: Dict[protocol.Token, "asyncio.Future[None]"]
    __handshake: Optional["asyncio.Future[None]"]
    __closed: "asyncio.Future[None]"
    __requests: Dict[RequestId, OutgoingRequestImpl]
    __subscriptions: Dict[ChannelName, Set[Subscription]]
    __promiscuous_callback: Optional[PromiscuousCallback]
    # __published: List[protocol.ClientPublish]
    __request_tasks: Set["asyncio.Future[None]"]

    def __init__(
        self,
        name: str,
        *,
        disconnected: Optional[Callable[[], None]] = None,
        persistent: bool = False,
        parallel_requests: int = 1,
        mode: Literal["immediate", "lazy"] = "immediate",
        accept_failure: bool = False,
    ):
        self.__id = secrets.token_hex(8)
        self.__counter = 0
        self.__name = name
        self.__token_counter = 0
        self.__futures = {}
        self.__disconnected = disconnected
        self.__persistent = persistent
        self.__mode = mode
        self.__accept_failure = accept_failure
        self.__closed = asyncio.Future()
        self.__requests = {}
        self.__parallel_requests = parallel_requests
        self.__connection = None
        self.__handshake = (
            asyncio.create_task(self.__connect()) if mode == "immediate" else None
        )
        self.__subscriptions = {}
        self.__promiscuous_callback = None
        # self.__published = []
        self.__request_tasks = set()

    def _token(self) -> protocol.Token:
        self.__token_counter += 1
        return protocol.Token(self.__token_counter)

    @property
    async def ready(self) -> None:
        if self.__handshake is None:
            self.__handshake = asyncio.create_task(self.__connect())
        await self.__handshake

    @property
    async def closed(self) -> None:
        await self.__closed

    async def request(
        self, payload: Payload, channel_name: ChannelName
    ) -> OutgoingRequest:
        await self.ready
        request_id = RequestId(f"{self.__id}:{self.__counter}")
        self.__counter += 1
        request = self.__requests[request_id] = OutgoingRequestImpl()
        await self.__write(
            protocol.ClientRequest(self._token(), channel_name, request_id, payload)
        )
        return request

    async def publish(
        self, cursor: dbaccess.TransactionCursor, message: PublishMessage
    ) -> Awaitable[None]:
        channel_names = message.channel_names
        payload = message.payload

        async with dbaccess.Query[ReservationId](
            cursor,
            """SELECT reservation_id
                 FROM pubsubreservations
                WHERE channel=ANY ({channel_names})""",
            channel_names=list(channel_names),
        ) as result:
            reservation_ids = await result.scalars()
        if reservation_ids:
            message_id = await cursor.insert(
                "pubsubmessages",
                {"payload": pickle.dumps(payload)},
                returning="message_id",
                value_type=protocol.MessageId,
            )
            await cursor.insertmany(
                "pubsubreservedmessages",
                (
                    dbaccess.parameters(
                        reservation_id=reservation_id, message_id=message_id
                    )
                    for reservation_id in reservation_ids
                ),
            )
            reservations = [
                protocol.Reservation(reservation_id, message_id)
                for reservation_id in reservation_ids
            ]
            logger.debug(
                f"reserved message: {payload=} {channel_names=} {reservations=}"
            )
        else:
            reservations = []

        client_publish = protocol.ClientPublish(
            self._token(), tuple(channel_names), payload, reservations
        )
        future = self.__futures[
            client_publish.token
        ] = asyncio.get_running_loop().create_future()

        async def flush() -> None:
            try:
                await self.ready
            except Exception as error:
                logger.debug("message not sent: Pub/Sub not answering")
                return

            assert self.__connection

            logger.debug("outgoing: %r", client_publish)

            try:
                await self.__connection.write_message(client_publish)
            except Exception as error:
                logger.exception(f"failed to send message: {error}")

        async def commit_callback() -> None:
            await flush()

        async def rollback_callback() -> None:
            future.cancel()

        cursor.transaction.add_commit_callback(commit_callback)
        cursor.transaction.add_rollback_callback(rollback_callback)

        return future

    async def subscribe(
        self,
        channel_name: ChannelName,
        callback: MessageCallback,
        *,
        reservation_id: Optional[ReservationId] = None,
    ) -> SubscriptionImpl:
        await self.ready
        assert not self.__promiscuous_callback
        subscription = SubscriptionImpl(
            self, channel_name, callback, None, reservation_id
        )
        subscriptions = self.__subscriptions.setdefault(channel_name, set())
        subscriptions.add(subscription)
        if len(subscriptions) == 1 or reservation_id is not None:
            await self.__write(
                protocol.ClientSubscribe(self._token(), channel_name, reservation_id)
            )
        return subscription

    async def subscribe_promiscuous(self, callback: PromiscuousCallback) -> None:
        await self.ready
        assert not self.__subscriptions
        self.__promiscuous_callback = callback
        await self.__write(protocol.ClientSubscribe(self._token()))

    # @overload
    # async def unsubscribe(self, *, channel_name: ChannelName) -> None:
    #     ...

    # @overload
    # async def unsubscribe(self, *, subscription: Subscription) -> None:
    #     ...

    async def unsubscribe(
        self,
        *,
        channel_name: Optional[ChannelName] = None,
        subscription: Optional[Subscription] = None,
    ) -> None:
        await self.ready
        assert (channel_name is None) != (subscription is None)
        if subscription is not None:
            channel_name = subscription.channel_name
        assert channel_name
        subscriptions = self.__subscriptions.get(channel_name)
        if not subscriptions:
            return
        if subscription is not None:
            subscriptions.remove(subscription)
        else:
            subscriptions = None
        if not subscriptions:
            await self.__write(protocol.ClientUnsubscribe(self._token(), channel_name))
            del self.__subscriptions[channel_name]
        elif subscription is not None and subscription.reservation_id:
            await self.__write(
                protocol.ClientUnsubscribe(
                    self._token(), channel_name, subscription.reservation_id
                )
            )

    async def handle_requests(
        self,
        channel_name: ChannelName,
        callback: RequestCallback,
    ) -> SubscriptionImpl:
        await self.ready
        subscription = SubscriptionImpl(self, channel_name, None, callback)
        subscriptions = self.__subscriptions.setdefault(channel_name, set())
        subscriptions.add(subscription)
        if len(subscriptions) == 1:
            await self.__write(
                protocol.ClientHandleRequests(self._token(), channel_name)
            )
        return subscription

    # Internal functions.

    async def __handle_server_publish(self, message: protocol.ServerPublish) -> None:
        if self.__promiscuous_callback:
            asyncio.ensure_future(
                invoke_promiscuous_callback(
                    self.__promiscuous_callback,
                    message.channels,
                    Message(message.payload),
                )
            )
            return

        (channel_name,) = message.channels

        def create_message() -> Message:
            if subscription.reservation_id is not None:
                for reservation in message.reservations:
                    if reservation.reservation_id != subscription.reservation_id:
                        continue
                    return ReservedMessage(
                        message.payload,
                        functools.partial(
                            self.__write,
                            protocol.ClientPublishConfirmation(
                                self._token(), reservation
                            ),
                        ),
                    )
            return Message(message.payload)

        for subscription in self.__subscriptions[channel_name]:
            if not subscription.message_callback:
                continue
            if subscription.reservation_id is not None:
                for reservation in message.reservations:
                    if reservation.reservation_id == subscription.reservation_id:
                        break
                else:
                    continue
            asyncio.ensure_future(
                invoke_message_callback(
                    subscription.message_callback,
                    channel_name,
                    create_message(),
                )
            )

    async def __handle_server_request(self, message: protocol.ServerRequest) -> None:
        for subscription in self.__subscriptions[message.channel]:
            if not subscription.request_callback:
                continue
            incoming_request = IncomingRequestImpl(
                functools.partial(self.__write, message.delivery(self._token())),
                functools.partial(self.__notify_result, message),  # type: ignore
                message.request_id,
                message.payload,
            )

            def done(future: "asyncio.Future[None]") -> None:
                try:
                    future.result()
                except Exception:
                    logger.exception("request callback crashed")
                finally:
                    self.__request_tasks.remove(future)

            future = asyncio.create_task(
                invoke_request_callback(
                    subscription.request_callback, message.channel, incoming_request
                )
            )
            self.__request_tasks.add(future)
            future.add_done_callback(done)

    async def __incoming(self, message: Optional[Any] = None) -> None:
        if message is None:
            logger.debug("connection closed")
            if self.__disconnected:
                self.__disconnected()
            self.__closed.set_result(None)
            self.__connection = None
            return

        if isinstance(message, protocol.ServerAck):
            try:
                future = self.__futures.pop(message.token)
            except KeyError:
                logger.warning("Unexpected Ack received: %r", message)
            else:
                # if not future.cancelled:
                future.set_result(None)
            return

        logger.debug(f"incoming: {message=}")

        if isinstance(message, protocol.ServerClose):
            logger.debug("received server close")
            if self.__connection:
                asyncio.create_task(self.__connection.close())
            return

        if isinstance(message, protocol.ServerPublish):
            await self.__handle_server_publish(message)
            return

        if isinstance(message, protocol.ServerRequest):
            await self.__handle_server_request(message)
            return

        if isinstance(
            message, (protocol.ServerRequestDelivery, protocol.ServerRequestResult)
        ):
            outgoing_request = self.__requests[message.request_id]
            request_future: "asyncio.Future[Any]"
            if isinstance(message, protocol.ServerRequestDelivery):
                request_future = outgoing_request.delivery
            else:
                request_future = outgoing_request.response
            if isinstance(message.response, protocol.Error):
                request_future.set_exception(RequestError(message.response.message))
            elif isinstance(message.response, protocol.Value):
                request_future.set_result(message.response.value)
            else:
                request_future.set_result(None)
            return

        logger.warning("Unexpected message received: %r", message)

    async def __write(self, message: protocol.ClientMessage) -> None:
        if not self.__connection:
            raise Exception("not connected")
        self.__futures[message.token] = self.__connection.loop.create_future()
        logger.debug("outgoing: %r", message)
        await self.__connection.write_message(message)
        await self.__futures[message.token]

    # async def __flush(self) -> None:
    #     assert self.__connection
    #     loop = asyncio.get_running_loop()
    #     futures = []
    #     for message in self.__published:
    #         future = self.__futures[message.token] = loop.create_future()
    #         futures.append(future)
    #         logger.debug("outgoing: %r", message)
    #         await self.__connection.write_message(message)
    #     await asyncio.wait(futures)

    async def __notify_result(
        self,
        request: protocol.ServerRequest,
        *,
        value: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        await self.__write(
            request.result(
                self._token(),
                protocol.Value(value) if message is None else protocol.Error(message),
            )
        )

    async def __connect(self) -> None:
        while True:
            try:
                self.__connection = MessageChannel[
                    protocol.ClientMessage, protocol.ServerMessage
                ]("pubsub", dispatch_message=self.__incoming)
                await self.__write(
                    protocol.ClientHello(
                        self._token(),
                        self.__name,
                        os.getpid(),
                        self.__parallel_requests,
                    )
                )
            except ServiceError as error:
                if self.__connection:
                    await self.__connection.close()
                self.__connection = None
                logger.debug("connection attempt failed: %s", str(error))
                if not self.__persistent:
                    raise Error("Failed to connect to pub/sub service")
                await asyncio.sleep(1)
            else:
                break

    async def close(self) -> None:
        if self.__connection and not self.__closed.done():
            await self.__write(protocol.ClientClose(self._token()))
            await self.__connection.close()
            self.__connection = None

    async def __aenter__(self) -> ClientImpl:
        if self.__mode != "lazy":
            await self.ready
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is not None:
            return
        if self.__mode == "lazy" and self.__futures:
            try:
                await self.ready
            except Exception:
                if self.__accept_failure:
                    logger.info("Failed to establish pub/sub connection")
                    return
                raise
        if self.__connection and not self.__closed.done():
            if self.__futures:
                await asyncio.wait(self.__futures.values())
            await self.__connection.close()
            self.__connection = None


@connectImpl
def connect(
    client_name: str,
    disconnected: Optional[Callable[[], None]],
    persistent: bool,
    parallel_requests: int,
    mode: Literal["immediate", "lazy"],
    accept_failure: bool,
) -> AsyncContextManager[Client]:
    return ClientImpl(
        client_name,
        disconnected=disconnected,
        persistent=persistent,
        parallel_requests=parallel_requests,
        mode=mode,
        accept_failure=accept_failure,
    )


@publishImpl
async def publish(
    critic: api.critic.Critic, client_name: str, messages: Sequence[PublishMessage]
) -> None:
    async with ClientImpl(client_name) as client:
        async with critic.transaction() as cursor:
            for message in messages:
                await client.publish(cursor, message)
