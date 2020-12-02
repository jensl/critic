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
import multiprocessing
from typing import Dict, Literal, Optional, Set, Tuple

logger = logging.getLogger("critic.background.differenceengine")

from .jobrunner import JobRunner
from critic import api
from critic import background
from critic.api.transaction.protocol import ModifiedAPIObject
from critic import pubsub


Command = Tuple[Literal["monitor", "update", "forget"], int]


class ChangesetsMonitor:
    __levels: Dict[int, Set[api.changeset.CompletionLevel]]
    __commands: "asyncio.Queue[Command]"

    def __init__(self, service: DifferenceEngine):
        self.__service = service
        self.__levels = {}  # { changeset_id => set() }
        self.__commands = asyncio.Queue()

        service.check_future(self.__run())

    async def __update(self, critic: api.critic.Critic, changeset_id: int) -> None:
        old_levels = self.__levels.get(changeset_id, set())
        changeset = await api.changeset.fetch(critic, changeset_id)
        new_levels = self.__levels[changeset_id] = await changeset.completion_level

        if old_levels is None or new_levels - old_levels:
            self.__service.check_future(
                self.__service.publish_message(
                    ModifiedAPIObject(
                        "changesets",
                        changeset_id,
                        {"completion_level": sorted(new_levels)},
                    ),
                    f"changesets/{changeset_id}",
                )
            )

    async def __run(self) -> None:
        try:
            while True:
                commands = [await self.__commands.get()]
                try:
                    while True:
                        commands.append(self.__commands.get_nowait())
                except asyncio.QueueEmpty:
                    pass
                async with self.__service.start_session() as critic:
                    for command, changeset_id in commands:
                        if command == "monitor":
                            assert changeset_id not in self.__levels
                        else:
                            assert changeset_id in self.__levels
                        await self.__update(critic, changeset_id)
                        if command == "forget":
                            del self.__levels[changeset_id]
        except asyncio.CancelledError:
            pass

    def __put_command(self, command: Command) -> None:
        self.__service.check_coroutine_threadsafe(self.__commands.put(command))

    def monitor(self, changeset_id: int) -> None:
        self.__put_command(("monitor", changeset_id))

    def update(self, changeset_id: int) -> None:
        self.__put_command(("update", changeset_id))

    def forget(self, changeset_id: int) -> None:
        self.__put_command(("forget", changeset_id))


class DifferenceEngine(background.service.BackgroundService):
    name = "differenceengine"
    want_pubsub = True

    # def will_start(self):
    #     return False

    runner: Optional[JobRunner]
    runner_future: Optional["asyncio.Future[None]"]

    async def did_start(self) -> None:
        self.runner = JobRunner(self)
        self.runner_future = None

        if "maintenance_at" in self.service_settings:
            self.register_maintenance(
                self.perform_maintenance, self.service_settings.maintenance_at
            )

        self.__changesets_monitor = ChangesetsMonitor(self)

    async def pubsub_connected(self, client: pubsub.Client, /) -> None:
        async def notify_runner(
            channel_name: pubsub.ChannelName, message: pubsub.Message
        ) -> None:
            if self.runner:
                await self.runner.new_changesets()

        await client.subscribe(pubsub.ChannelName("changesets"), notify_runner)

        if self.runner and not self.runner_future:
            self.runner_future = self.check_future(self.runner.run())

    async def wake_up(self) -> None:
        if self.runner:
            await self.runner.new_changesets()

    # def is_idle(self) -> bool:
    #     return not self.runner or self.runner.is_idle

    # async def wait_for_idle(self, timeout: float) -> None:
    #     loop = self.loop
    #     future = self.loop.create_future()

    #     def callback() -> None:
    #         loop.call_soon_threadsafe(future.set_result, True)

    #     if self.runner and self.runner.set_idle_callback(callback):
    #         logger.debug("waiting for JobRunner to become idle")
    #         await asyncio.wait_for(future, timeout, loop=loop)

    async def will_stop(self) -> None:
        logger.debug("stopping job runner")

        if self.runner:
            await self.runner.terminate()
        if self.runner_future:
            await self.runner_future

        logger.debug("job runner stopped")

    async def publish_message(self, message: object, channel_name: str) -> None:
        pubsub_client = await self.pubsub_client
        async with self.start_session() as critic:
            async with critic.transaction() as cursor:
                await pubsub_client.publish(
                    cursor,
                    pubsub.PublishMessage(
                        pubsub.ChannelName(channel_name), pubsub.Payload(message)
                    ),
                )

    def monitor_changeset(self, changeset_id: int) -> None:
        self.__changesets_monitor.monitor(changeset_id)

    def update_changeset(self, changeset_id: int) -> None:
        self.__changesets_monitor.update(changeset_id)

    def forget_changeset(self, changeset_id: int) -> None:
        self.__changesets_monitor.forget(changeset_id)

    async def perform_maintenance(self) -> None:
        logger.debug("FIXME: maintenance not implemented")


if __name__ == "__main__":
    multiprocessing.set_start_method("forkserver")
    background.service.call(DifferenceEngine)
