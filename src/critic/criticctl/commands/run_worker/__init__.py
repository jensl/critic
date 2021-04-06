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

import argparse
import asyncio
from asyncio.events import AbstractEventLoop
import functools
import logging
import signal
from typing import Any, Callable, List, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic.base.profiling import Profiler
from critic import pubsub

from .analyzechangedlines import handle_analyzechangedlines
from .databaseupdater import DatabaseUpdater
from .error import Error
from .session import Session
from .syntaxhighlightfile import handle_syntaxhighlightfile

name = "run-worker"
title = "Run worker"


Callback = Callable[
    [asyncio.AbstractEventLoop, object, Session, DatabaseUpdater, Profiler], Any
]


class Handler:
    async def __call__(
        self,
        callback: Callback,
        session: Session,
        database_updater: DatabaseUpdater,
        profiler: Profiler,
        channel_name: pubsub.ChannelName,
        request: pubsub.IncomingRequest,
    ) -> None:
        logger.debug(
            "%s: handle_request: channel_name=%r", request.request_id, channel_name
        )

        with profiler.check("request.notify_delivery()"):
            await request.notify_delivery()

        try:
            response = await callback(
                asyncio.get_running_loop(),
                request.payload,
                session,
                database_updater,
                profiler,
            )
        except Error as error:
            with profiler.check("request.notify_error()"):
                await request.notify_error(str(error))
        else:
            with profiler.check("request.notify_response()"):
                await request.notify_response(response)

        logger.debug("%s: handle_request: done", request.request_id)


def setup(parser: argparse.ArgumentParser) -> None:
    pass


CALLBACKS: List[Tuple[pubsub.ChannelName, Callback]] = [
    (pubsub.ChannelName("syntaxhighlightfile"), handle_syntaxhighlightfile),
    (pubsub.ChannelName("analyzechangedlines"), handle_analyzechangedlines),
]


def set_event_threadsafe(event: asyncio.Event) -> Callable[[], None]:
    def set_event(loop: AbstractEventLoop, event: asyncio.Event) -> None:
        loop.call_soon_threadsafe(event.set)

    return functools.partial(set_event, asyncio.get_running_loop(), event)


async def run(stopped: asyncio.Event) -> None:
    handler = Handler()
    database_updater = DatabaseUpdater(set_event_threadsafe(stopped))
    database_updater.start()
    profiler = Profiler()

    try:
        async with Session.start() as session:
            async with pubsub.connect(f"worker", parallel_requests=100) as client:
                for channel_name, callback in CALLBACKS:
                    await client.handle_requests(
                        channel_name,
                        functools.partial(
                            handler, callback, session, database_updater, profiler
                        ),
                    )
                await stopped.wait()
    except Exception:
        logger.exception("Failed to connect to PubSub and subscribe to channels!")
        stopped.set()
    finally:
        logger.info("\n%s", profiler.output())

    database_updater.stop()


async def main(critic: api.critic.Critic, arguments: Any) -> None:
    await critic.close()

    stopped = asyncio.Event()

    def handle_sigint(*args: object) -> None:
        logger.debug("sigint received")
        stopped.set()

    def handle_sigterm(*args: object) -> None:
        logger.debug("sigterm received")
        stopped.set()

    critic.loop.add_signal_handler(signal.SIGINT, handle_sigint)
    critic.loop.add_signal_handler(signal.SIGTERM, handle_sigterm)

    await run(stopped)
