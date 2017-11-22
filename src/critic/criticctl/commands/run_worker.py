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
import signal
from typing import Any, Callable, List, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic import pubsub
from critic.background.differenceengine.protocol import (
    AnalyzeChangedLines,
    SyntaxHighlighFile,
)

name = "run-worker"
title = "Run worker"


class Error(Exception):
    pass


async def handle_syntaxhighlightfile(
    loop: asyncio.AbstractEventLoop, request: pubsub.IncomingRequest
) -> SyntaxHighlighFile.Response:
    from critic.syntaxhighlight.generate import LanguageNotSupported, generate

    assert isinstance(request.payload, SyntaxHighlighFile.Request)

    source = request.payload.source
    language = request.payload.language

    logger.info("%s: handle_syntaxhighlight: language=%s", request.request_id, language)

    try:
        lines, contexts = await loop.run_in_executor(None, generate, source, language)
    except LanguageNotSupported:
        raise Error(f"{language}: language not supported")
    else:
        return SyntaxHighlighFile.Response(lines, contexts)


async def handle_analyzechangedlines(
    loop: asyncio.AbstractEventLoop, request: pubsub.IncomingRequest
) -> AnalyzeChangedLines.Response:
    from critic.diff.analyze import analyzeChunk

    assert isinstance(request.payload, AnalyzeChangedLines.Request)

    old_lines = request.payload.old_lines
    new_lines = request.payload.new_lines

    logger.info("%s: handle_analyzechangedlines", request.request_id)

    analysis = await loop.run_in_executor(None, analyzeChunk, old_lines, new_lines)

    if analysis is None:
        logger.info("%s: no analysis: %r %r", request.request_id, old_lines, new_lines)
    else:
        logger.info("%s: analysis: %r", request.request_id, analysis)

    return AnalyzeChangedLines.Response(analysis)


Callback = Callable[[asyncio.AbstractEventLoop, pubsub.IncomingRequest], Any]


class Handler:
    async def __call__(
        self,
        callback: Callback,
        channel_name: pubsub.ChannelName,
        request: pubsub.IncomingRequest,
    ) -> None:
        logger.info(
            "%s: handle_request: channel_name=%r", request.request_id, channel_name
        )

        await request.notify_delivery()

        try:
            response = await callback(asyncio.get_running_loop(), request)
        except Error as error:
            await request.notify_error(str(error))
        else:
            await request.notify_response(response)


def setup(parser):
    pass


CALLBACKS: List[Tuple[pubsub.ChannelName, Callback]] = [
    (pubsub.ChannelName("syntaxhighlightfile"), handle_syntaxhighlightfile),
    (pubsub.ChannelName("analyzechangedlines"), handle_analyzechangedlines),
]


async def run(stopped: asyncio.Event) -> None:
    handler = Handler()

    try:
        async with pubsub.connect(f"worker") as client:
            for channel_name, callback in CALLBACKS:
                await client.handle_requests(
                    channel_name, functools.partial(handler, callback),
                )
            await stopped.wait()
    except Exception:
        logger.exception("Failed to connect to PubSub and subscribe to channels!")
        stopped.set()


async def main(critic: api.critic.Critic, arguments: Any) -> None:
    await critic.close()

    stopped = asyncio.Event()

    def handle_sigint(*args):
        logger.debug("sigint received")
        stopped.set()

    def handle_sigterm(*args):
        logger.debug("sigterm received")
        stopped.set()

    critic.loop.add_signal_handler(signal.SIGINT, handle_sigint)
    critic.loop.add_signal_handler(signal.SIGTERM, handle_sigterm)

    await run(stopped)
