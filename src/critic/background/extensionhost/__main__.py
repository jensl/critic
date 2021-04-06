# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2019 the Critic contributors, Opera Software ASA
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

import asyncio
import logging
import multiprocessing
import os
import secrets
import sys
from typing import Any, Awaitable, Dict, List, Literal, Tuple, cast

logger = logging.getLogger("critic.background.extensionhost")

from . import (
    CallError,
    CallRequest,
    CallResponse,
    SubscriptionMessage,
    SubscriptionResponseItem,
    SubscriptionRole,
)
from ..service import BackgroundService, call
from critic import api
from critic import base
from critic import pubsub
from critic.base import binarylog


class ExtensionHostService(BackgroundService):
    name = "extensionhost"
    want_pubsub = True

    __subscriptions: Dict[pubsub.ReservationId, pubsub.Subscription]
    __subscribers: Dict[pubsub.ChannelName, Dict[Tuple[int, int], pubsub.ReservationId]]
    __processes: Dict[
        int, Tuple[asyncio.subprocess.Process, "asyncio.Future[Literal[True]]"]
    ]

    def __init__(self) -> None:
        super().__init__()
        self.__subscriptions = {}
        self.__subscribers = {}
        self.__processes = {}

    def will_start(self) -> bool:
        if not self.settings.extensions.enabled:
            logger.info("Extension support not enabled")
            return False
        return True

    async def did_start(self) -> None:
        self.__desired = self.settings.services.extensionhost.workers
        if self.__desired < 0:
            self.__desired = multiprocessing.cpu_count()

    async def will_stop(self) -> None:
        futures = []
        for (process, future) in self.__processes.values():
            process.terminate()
            futures.append(future)
        if futures:
            await asyncio.wait(futures)

    async def call_extension(
        self,
        version_id: int,
        channel_name: pubsub.ChannelName,
        message: pubsub.Message,
    ) -> None:
        request_id = secrets.token_bytes(8)
        client = await self.pubsub_client
        handle = await client.request(
            pubsub.Payload(
                CallRequest(
                    version_id,
                    "system",
                    None,
                    SubscriptionRole(
                        SubscriptionMessage(request_id, channel_name, message.payload)
                    ),
                )
            ),
            pubsub.ChannelName("extension/call"),
        )
        await handle.delivery
        response = await handle.response
        assert isinstance(response, CallResponse)
        if response.success:
            if isinstance(message, pubsub.ReservedMessage):
                await message.notify_delivery()  # type: ignore
        for item in response.items:
            if isinstance(item, CallError):
                logger.error(item.message)
                if item.details:
                    logger.error(item.details)
            if isinstance(item, SubscriptionResponseItem):
                if item.error:
                    logger.error(item.error)

    async def handle_message(
        self, channel_name: pubsub.ChannelName, message: pubsub.Message
    ) -> None:
        logger.debug(f"{channel_name=} {message=}")
        for (version_id, installation_id) in self.__subscribers.get(channel_name, ()):
            logger.debug(
                f"incoming: {installation_id=} {channel_name=} {message.payload=!r}"
            )
            self.check_future(self.call_extension(version_id, channel_name, message))

    async def pubsub_connected(self, client: pubsub.Client, /) -> None:
        async def handle_message(
            channel_name: pubsub.ChannelName, message: pubsub.Message
        ) -> None:
            self.do_wake_up()

        await client.subscribe(
            pubsub.ChannelName("extensioninstallations"), handle_message
        )

        if self.__desired:
            self.check_future(self.__ensure_processes())

        self.__subscribers = {}
        self.__subscriptions = {}
        self.do_wake_up()

    async def wake_up(self) -> None:
        await self.update_reservations()

    async def update_reservations(self) -> None:
        logger.debug("updating reservations...")

        client = await self.pubsub_client
        subscriptions: Dict[
            pubsub.ChannelName, Dict[Tuple[int, int], pubsub.ReservationId]
        ] = {}
        async with self.start_session() as critic:
            async with api.critic.Query[
                Tuple[int, int, pubsub.ChannelName, pubsub.ReservationId]
            ](
                critic,
                """SELECT version, install_id, channel, reservation_id
                     FROM extensionpubsubreservations
                     JOIN extensioninstalls ON (extensioninstalls.id=install_id)
                     JOIN pubsubreservations USING (reservation_id)""",
            ) as result:
                async for version_id, installation_id, channel_name, reservation_id in result:
                    per_channel = subscriptions.setdefault(channel_name, {})
                    per_channel[(version_id, installation_id)] = reservation_id

        for channel_name, per_channel in subscriptions.items():
            if channel_name not in self.__subscribers:
                old_reservation_ids = set()
            else:
                old_reservation_ids = set(
                    reservation_id
                    for reservation_id in self.__subscribers[channel_name].values()
                    if reservation_id is not None
                )
            new_reservation_ids = set(
                reservation_id
                for reservation_id in per_channel.values()
                if reservation_id is not None
            )
            for reservation_id in new_reservation_ids - old_reservation_ids:
                self.__subscriptions[reservation_id] = await client.subscribe(
                    channel_name, self.handle_message, reservation_id=reservation_id
                )
            for reservation_id in old_reservation_ids - new_reservation_ids:
                if reservation_id in self.__subscriptions:
                    await client.unsubscribe(
                        subscription=self.__subscriptions[reservation_id]
                    )
            self.__subscribers[channel_name] = per_channel

        logger.debug(f"{self.__subscribers=}")

        for channel_name in list(self.__subscribers.keys()):
            if channel_name not in subscriptions:
                logger.debug("%s: unsubscribing from channel", channel_name)
                await client.unsubscribe(channel_name=channel_name)
                for reservation_id in self.__subscribers.pop(channel_name).values():
                    del self.__subscriptions[reservation_id]

    async def __run_process(self) -> None:
        process = await asyncio.create_subprocess_exec(
            os.path.join(sys.prefix, "bin", "criticctl"),
            "--verbose",
            "--binary-output",
            "run-extensionhost",
            "--base-dir",
            base.configuration()["paths.home"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        future = self.loop.create_future()

        logger.info("Started worker [pid=%d]", process.pid)

        self.__processes[process.pid] = (process, future)

        async def handle_stdout() -> None:
            assert process.stdout
            async for msg in binarylog.read(process.stdout):
                if isinstance(msg, dict) and "log" in msg:
                    binarylog.emit(
                        cast(binarylog.BinaryLogRecord, msg["log"]),
                        suffix=str(process.pid),
                    )

        async def handle_stderr() -> None:
            assert process.stderr
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                logger.log(logging.DEBUG, "STDERR: %s", line.decode().rstrip())

        async def wait() -> None:
            tasks: List[Awaitable[Any]] = [
                self.check_future(handle_stdout()),
                self.check_future(handle_stderr()),
                self.check_future(process.wait()),
            ]
            await asyncio.wait(tasks)

            logger.info(
                "Worker stopped [pid=%d, returncode=%d]",
                process.pid,
                process.returncode,
            )

            del self.__processes[process.pid]

            future.set_result(True)

        self.check_future(wait())

    async def __ensure_processes(self) -> None:
        while len(self.__processes) < self.__desired:
            await self.__run_process()

    # async def build_wheel(self):
    #     def find_wheels():
    #         return glob.glob(
    #             os.path.join(base.configuration()["paths.home"], "critic-*.whl")
    #         )

    #     for wheel in find_wheels():
    #         logger.debug("%s: unlinking existing wheel", wheel)
    #         os.unlink(wheel)

    #     process = await asyncio.create_subprocess_exec(
    #         os.path.join(sys.prefix, "bin", "pip"), "wheel", "--no-deps"
    #     )


if __name__ == "__main__":
    call(ExtensionHostService)
