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
import logging
import pickle
import time
from typing import (
    Any,
    AsyncIterator,
    Collection,
    Deque,
    Dict,
    Literal,
    Optional,
    Set,
    Tuple,
    overload,
)
from collections import defaultdict, deque
from contextlib import asynccontextmanager

logger = logging.getLogger("critic.background.pubsub")

from critic import api

from . import protocol
from ..binaryprotocol import BinaryProtocolClient, BinaryProtocol
from ..service import BackgroundService, call


class PubSubClient(
    BinaryProtocolClient[protocol.ClientMessage, protocol.ServerMessage]
):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.name = "(unknown)"
        self.pid: Optional[int] = None
        self.parallel_requests: int = 1
        self.reservation_ids: Optional[Set[protocol.ReservationId]] = None
        self.queue: Deque[protocol.ServerMessage] = deque()
        self.pending_messages: Set[protocol.Reservation] = set()
        self.condition = asyncio.Condition()
        self.__is_disconnecting = False

    def __repr__(self) -> str:
        return f"<Client name={self.name!r} pid={self.pid}>"

    async def deliver_messages(self) -> None:
        try:
            while True:
                message: protocol.ServerMessage
                async with self.condition:
                    while not (self.queue or self.__is_disconnecting):
                        await self.condition.wait()
                    if self.__is_disconnecting:
                        break
                    message = self.queue.popleft()
                try:
                    self.write_message(message)
                except Exception:
                    logger.error("failed to write message: %r", message)
                    raise
                if isinstance(message, protocol.ServerClose):
                    await self.writer.drain()
                    self.writer.write_eof()
                    break
        except Exception:
            logger.exception("PubSubClient.deliver_messages() crashed!")
            raise

    async def disconnecting(self) -> None:
        async with self.condition:
            self.__is_disconnecting = True
            self.condition.notify()

    async def deliver(self, message: protocol.ServerMessage) -> None:
        async with self.condition:
            # if isinstance(message, protocol.ServerPublish) and message.reservations:
            #     if message.reservation in self.pending_messages:
            #         return
            #     self.pending_messages.add(message.reservation)
            self.queue.append(message)
            self.condition.notify()


TOKEN = protocol.Token(-1)


class Channel:
    subscribers: Dict[PubSubClient, Set[protocol.ReservationId]]
    reservation_ids: Set[protocol.ReservationId]
    acquired: Dict[PubSubClient, int]

    def __init__(
        self, service: PubSubService, name: protocol.ChannelName, for_requests: bool
    ):
        self.service = service
        self.name = name
        self.for_requests = for_requests
        self.subscribers = {}
        self.reservation_ids = set()
        self.acquired = {}
        self.condition = asyncio.Condition()

    @property
    def empty(self) -> bool:
        return not self.subscribers and not self.reservation_ids

    @property
    def key(self) -> Tuple[str, bool]:
        return (self.name, self.for_requests)

    def __repr__(self) -> str:
        return f"<Channel name={self.name!r} id={id(self)!r}>"

    async def subscribe(
        self, client: PubSubClient, reservation_id: Optional[protocol.ReservationId]
    ) -> None:
        async with self.condition:
            logger.debug("%r: client subscribed: %r", self, client)
            reservation_ids = self.subscribers.setdefault(client, set())
            if reservation_id is not None:
                reservation_ids.add(reservation_id)
                self.reservation_ids.add(reservation_id)
            self.condition.notify_all()

    def unsubscribe(
        self,
        client: PubSubClient,
        reservation_id: Optional[protocol.ReservationId] = None,
    ) -> None:
        if reservation_id is None:
            self.reservation_ids.difference_update(self.subscribers.pop(client, set()))
        else:
            self.subscribers[client].remove(reservation_id)
            self.reservation_ids.remove(reservation_id)

    async def publish(
        self,
        payload: protocol.Payload,
        from_client: PubSubClient,
        *,
        reservations: Collection[protocol.Reservation],
    ) -> None:
        assert not self.for_requests

        if self.subscribers:
            for client, reservation_ids in self.subscribers.items():
                if client is from_client:
                    continue
                await client.deliver(
                    protocol.ServerPublish(
                        (self.name,),
                        payload,
                        [
                            reservation
                            for reservation in reservations
                            if reservation.reservation_id in reservation_ids
                        ],
                    )
                )

    @asynccontextmanager
    async def acquire(self, timeout: float) -> AsyncIterator[PubSubClient]:
        assert self.for_requests

        async def pick_subscriber() -> PubSubClient:
            logger.debug(
                "%r: picking subscriber...\n  %r\n  %r",
                self,
                self.subscribers,
                self.acquired,
            )
            async with self.condition:
                while True:
                    candidate = None
                    candidate_available = 0
                    for subscriber in self.subscribers.keys():
                        current_requests = self.acquired.get(subscriber, 0)
                        available = subscriber.parallel_requests - current_requests
                        if available > candidate_available:
                            candidate = subscriber
                            candidate_available = available
                    if candidate:
                        break
                    logger.debug("%r: no subscribers available", self)
                    await self.condition.wait()
                self.acquired[candidate] = self.acquired.get(candidate, 0) + 1
                return candidate

        logger.debug("%r: acquiring subscriber...", self)

        subscriber = await asyncio.wait_for(pick_subscriber(), timeout)

        logger.debug("%r: subscriber acquired: %r", self, subscriber)

        try:
            yield subscriber
        finally:
            async with self.condition:
                logger.debug("%r: releasing subscriber: %r", self, subscriber)
                self.acquired[subscriber] -= 1
                self.condition.notify()


class Request:
    subscriber: Optional[PubSubClient]
    delivery: "asyncio.Future[None]"
    response: "asyncio.Future[Any]"

    def __init__(self) -> None:
        self.subscriber = None
        self.delivery = asyncio.get_running_loop().create_future()
        self.response = asyncio.get_running_loop().create_future()


class PubSubService(
    BackgroundService,
    BinaryProtocol[PubSubClient, protocol.ClientMessage, protocol.ServerMessage],
):
    name = "pubsub"

    channels: Dict[Tuple[str, bool], Channel]
    promiscuous: Set[PubSubClient]
    requests: Dict[str, Request]

    def __init__(self) -> None:
        super().__init__()
        self.channels = {}
        self.promiscuous = set()
        self.requests = {}

    @overload
    def get_channel(
        self, name: protocol.ChannelName, create: Literal[True], for_requests: bool
    ) -> Channel:
        ...

    @overload
    def get_channel(
        self, name: protocol.ChannelName, create: bool, for_requests: bool
    ) -> Optional[Channel]:
        ...

    def get_channel(
        self, name: protocol.ChannelName, create: bool, for_requests: bool
    ) -> Optional[Channel]:
        if (name, for_requests) not in self.channels:
            if not create:
                return None
            self.channels[(name, for_requests)] = Channel(self, name, for_requests)
        return self.channels[(name, for_requests)]

    async def print_stats(self) -> None:
        while not self.is_terminating:
            await asyncio.sleep(5)
            for name, channel in sorted(self.channels.items()):
                logger.debug("channel %r: %r", name, channel.subscribers)

    async def did_start(self) -> None:
        # self.check_future(self.print_stats())
        pass

    async def wake_up(self) -> None:
        await self.update_reservations()

    async def update_reservations(self) -> None:
        logger.info("Updating channel reservations")
        per_channel = defaultdict(set)
        async with self.start_session() as critic:
            async with critic.query(
                "SELECT reservation_id, channel FROM pubsubreservations"
            ) as result:
                async for reservation_id, channel_name in result:
                    per_channel[channel_name].add(reservation_id)
        for channel_name, reservation_ids in per_channel.items():
            logger.debug("reservations: %s: %r", channel_name, reservation_ids)
            self.get_channel(
                channel_name, True, False
            ).reservation_ids = reservation_ids

    def handle_connection(self) -> asyncio.StreamReaderProtocol:
        return BinaryProtocol.handle_connection(self)

    def create_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> PubSubClient:
        return PubSubClient(reader, writer)

    async def handle_request(
        self,
        client: PubSubClient,
        channel: Channel,
        message: protocol.ClientRequest,
        *,
        timeout: int = 60,
    ) -> None:
        assert channel.for_requests
        request_id = message.request_id
        logger.debug("%s: handling request", request_id)
        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                request = self.requests[request_id] = Request()
                async with channel.acquire(deadline - time.time()) as subscriber:
                    request.subscriber = subscriber
                    subscriber.write_message(message.forwarded_request())
                    try:
                        await asyncio.wait_for(
                            request.delivery, min(10, deadline - time.time())
                        )
                    except asyncio.TimeoutError:
                        logger.info(
                            "%s: timeout waiting for delivery request", request_id
                        )
                        continue
                    client.write_message(
                        message.delivery(
                            protocol.Target(subscriber.name, subscriber.pid)
                        )
                    )
                    logger.debug("%s: request delivered to subscriber", request_id)
                    try:
                        result = await asyncio.wait_for(
                            request.response, deadline - time.time()
                        )
                    except asyncio.TimeoutError:
                        logger.info("%s: timeout waiting for result", request_id)
                        client.write_message(
                            message.result(protocol.Error("timeout waiting for result"))
                        )
                        return
                    except Exception as error:
                        client.write_message(message.result(protocol.Error(str(error))))
                        return
                    client.write_message(message.result(protocol.Value(result)))
                    del self.requests[request_id]
                    logger.debug("%s: request processing finished", request_id)
                    return
        except asyncio.TimeoutError:
            client.write_message(
                message.delivery(
                    protocol.Error("timeout waiting for available subscriber")
                )
            )

    async def dispatch_message(
        self, client: PubSubClient, message: protocol.ClientMessage
    ) -> AsyncIterator[protocol.ServerMessage]:
        def get_channels(
            *names: protocol.ChannelName, create: bool, for_requests: bool
        ) -> Set[Channel]:
            return {
                channel
                for name in names
                if (channel := self.get_channel(name, create, for_requests))
            }

        logger.debug(f"dispatch: {client=} {message=}")

        if isinstance(message, protocol.ClientHello):
            logger.debug(
                "client says hello: %s [pid=%d]", message.name, message.pid,
            )
            client.name = message.name
            client.pid = message.pid
            client.parallel_requests = message.parallel_requests
            self.check_future(client.deliver_messages())
        elif isinstance(message, protocol.ClientClose):
            logger.debug(
                "client says good buy: %r", client,
            )
        elif isinstance(message, protocol.ClientPublish):
            channels = set()
            for channel_name in message.channels:
                while channel_name:
                    channels.update(
                        get_channels(channel_name, create=False, for_requests=False)
                    )
                    channel_prefix, _, _ = str(channel_name).rpartition("/")
                    channel_name = protocol.ChannelName(channel_prefix)
            if channels:
                logger.debug(
                    "publishing to channels:\n  %s",
                    "\n  ".join(sorted(channel.name for channel in channels)),
                )
                for channel in channels:
                    await channel.publish(
                        message.payload, client, reservations=message.reservations
                    )
            for listener in self.promiscuous:
                logger.debug("publishing to promiscuous listener: %r", listener)
                await listener.deliver(
                    protocol.ServerPublish(message.channels, message.payload, [])
                )
        elif isinstance(message, protocol.ClientPublishConfirmation):
            await self.message_delivery_confirmed(message.reservation)
        elif isinstance(message, protocol.ClientRequest):
            self.check_future(
                self.handle_request(
                    client, self.get_channel(message.channel, True, True), message
                )
            )
        elif isinstance(message, protocol.ClientRequestDelivery):
            request = self.requests.get(message.request_id)
            if request:
                request.delivery.set_result(None)
        elif isinstance(message, protocol.ClientRequestResult):
            request = self.requests.get(message.request_id)
            if request:
                if isinstance(message.response, protocol.Value):
                    request.response.set_result(message.response.value)
                else:
                    request.response.set_exception(Exception(message.response.message))
        elif isinstance(message, protocol.ClientSubscribe):
            if message.channel is None:
                logger.debug("registering promiscuous listener: %r", client)
                self.promiscuous.add(client)
            else:
                for channel in get_channels(
                    message.channel, create=True, for_requests=False
                ):
                    logger.debug("subscribing client to channel: %s", channel.name)
                    await self.subscribe(client, channel, message.reservation_id)
        elif isinstance(message, protocol.ClientUnsubscribe):
            for channel in get_channels(
                message.channel, create=False, for_requests=False
            ):
                logger.debug("unsubscribing client from channel: %s", channel.name)
                channel.unsubscribe(client, message.reservation_id)
                if not channel:
                    del self.channels[channel.key]
        elif isinstance(message, protocol.ClientHandleRequests):
            for channel in get_channels(
                message.channel, create=True, for_requests=True
            ):
                logger.debug(
                    "subscribing client to channel (for requests): %s", channel.name
                )
                await self.subscribe(client, channel)
        else:
            logger.warning("Unexpected message: %r", message)

        yield message.ack()

    async def subscribe(
        self,
        client: PubSubClient,
        channel: Channel,
        reservation_id: protocol.ReservationId = None,
    ) -> None:
        await channel.subscribe(client, reservation_id)
        if reservation_id is not None:
            logger.debug(f"{reservation_id=}: checking stored reserved messages...")
            async with self.start_session() as critic:
                async with api.critic.Query[Tuple[protocol.MessageId, bytes]](
                    critic,
                    """SELECT message_id, payload
                         FROM pubsubmessages
                         JOIN pubsubreservedmessages USING (message_id)
                        WHERE reservation_id={reservation_id}
                        ORDER BY message_id ASC""",
                    reservation_id=reservation_id,
                ) as result:
                    messages = await result.all()
            if not messages:
                logger.debug(f"{reservation_id=}: no more stored messages")
            for message_id, payload in messages:
                logger.debug(
                    f"{reservation_id=}: delivering stored message: " f"{message_id=}"
                )
                await client.deliver(
                    protocol.ServerPublish(
                        (channel.name,),
                        pickle.loads(payload),
                        [protocol.Reservation(reservation_id, message_id)],
                    )
                )

    async def reserve_message(
        self,
        payload: protocol.Payload,
        reservation_ids: Collection[protocol.ReservationId],
    ) -> Optional[protocol.MessageId]:
        if not reservation_ids:
            return None
        logger.debug(f"reserving message: {payload=} {reservation_ids=}")
        async with self.start_session() as critic:
            async with critic.transaction() as cursor:
                message_id = await cursor.insert(
                    "pubsubmessages",
                    {"payload": pickle.dumps(payload)},
                    returning="message_id",
                )
                await cursor.insertmany(
                    "pubsubreservedmessages",
                    (
                        dict(reservation_id=reservation_id, message_id=message_id)
                        for reservation_id in reservation_ids
                    ),
                )
        logger.debug(f"reserved message stored: {message_id=} {reservation_ids=}")
        return message_id

    async def message_delivery_confirmed(
        self, reservation: protocol.Reservation
    ) -> None:
        reservation_id = reservation.reservation_id
        message_id = reservation.message_id
        logger.debug(f"{reservation_id=}: reserved message delivered: {message_id=}")
        async with self.start_session() as critic:
            async with critic.transaction() as cursor:
                await cursor.delete(
                    "pubsubreservedmessages",
                    reservation_id=reservation_id,
                    message_id=message_id,
                )
                async with cursor.query(
                    """SELECT 1
                         FROM pubsubreservedmessages
                        WHERE message_id={message_id}
                        LIMIT 1""",
                    message_id=message_id,
                ) as result:
                    prune_message = await result.empty()
                if prune_message:
                    cursor.delete("pubsubmessages", message_id=message_id)
                    logger.debug(f"{message_id=}: stored reserved message pruned")

    def client_connected(self, client: PubSubClient) -> None:
        logger.debug("client connected")

    def client_disconnected(self, client: PubSubClient) -> None:
        logger.debug("client disconnected: %s", client.name)
        empty_channels = set()
        for channel in self.channels.values():
            channel.unsubscribe(client)
            if channel.empty:
                empty_channels.add(channel)
        for channel in empty_channels:
            logger.debug("purging empty channel: %r", channel)
            del self.channels[channel.key]
        if client in self.promiscuous:
            logger.debug("removing promiscuous listener")
            self.promiscuous.remove(client)


if __name__ == "__main__":
    call(PubSubService)
