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
import functools
import logging
import os
import signal
from typing import Any, Callable

logger = logging.getLogger(__name__)


from critic import api
from critic import pubsub

from .arguments import Arguments
from .handlecall import handle_call
from .extension import Extension
from .state import STATE

name = "run-extensionhost"
title = "Run extension host"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-dir", default=os.environ.get("CRITIC_HOME"))
    parser.add_argument("--critic-wheel")


async def wrap_request(
    handler: Callable[[pubsub.IncomingRequest], Any],
    channel_name: pubsub.ChannelName,
    request: pubsub.IncomingRequest,
) -> None:
    try:
        await request.notify_delivery()
        response = await handler(request)
    except Exception as error:
        logger.exception("Crashed while handling request")
        await request.notify_error(str(error))
    else:
        await request.notify_response(response)


async def run(stopped: asyncio.Event) -> int:
    try:
        async with pubsub.connect(
            "extensionhost/runner", parallel_requests=10
        ) as client:
            await client.handle_requests(
                pubsub.ChannelName("extension/call"),
                functools.partial(wrap_request, handle_call),
            )
            await stopped.wait()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Failed to connect to PubSub and subscribe to channels!")
        stopped.set()
        return 1
    finally:
        await Extension.shutdown()
    return 0


async def main(critic: api.critic.Critic, arguments: Arguments) -> int:
    STATE.arguments = arguments

    assert STATE.base_dir

    stopped = asyncio.Event()

    critic.loop.add_signal_handler(signal.SIGINT, stopped.set)
    critic.loop.add_signal_handler(signal.SIGTERM, stopped.set)

    future = asyncio.ensure_future(run(stopped))

    await stopped.wait()

    if not future.done():
        future.cancel()

    return await future
