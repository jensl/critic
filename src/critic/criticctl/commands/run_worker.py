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
import signal
from typing import Any, Callable, List, Tuple, cast

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import pubsub
from critic.background.differenceengine.protocol import (
    AnalyzeChangedLines,
    SyntaxHighlighFile,
)
from critic.background.gitaccessor import GitRepositoryProxy
from critic.gitaccess import GitBlob
from critic.syntaxhighlight.generate import LanguageNotSupported, generate
from critic import textutils

name = "run-worker"
title = "Run worker"


class Error(Exception):
    pass


async def handle_syntaxhighlightfile(
    loop: asyncio.AbstractEventLoop, request: pubsub.IncomingRequest
) -> SyntaxHighlighFile.Response:
    assert isinstance(request.payload, SyntaxHighlighFile.Request)

    highlight_request = cast(SyntaxHighlighFile.Request, request.payload)

    async with GitRepositoryProxy.make(highlight_request.repository_path) as repository:
        source = textutils.decode(
            (
                await repository.fetchone(
                    highlight_request.sha1,
                    object_factory=GitBlob,
                    wanted_object_type="blob",
                )
            ).data
        )

    logger.debug(
        "%s: handle_syntaxhighlight: language=%s",
        request.request_id,
        highlight_request.language_label,
    )

    try:
        lines, contexts = await loop.run_in_executor(
            None, generate, source, highlight_request.language_label
        )
    except LanguageNotSupported:
        raise Error(f"{highlight_request.language_label}: language not supported")

    async with api.critic.startSession(for_system=True) as critic:
        async with critic.transaction() as cursor:
            await cursor.execute(
                """INSERT
                     INTO highlightfiles (
                            repository, sha1, language, conflicts
                          ) VALUES (
                            {repository_id}, {sha1}, {language_id}, {conflicts}
                          ) ON CONFLICT DO NOTHING""",
                repository_id=highlight_request.repository_id,
                sha1=highlight_request.sha1,
                language_id=highlight_request.language_id,
                conflicts=highlight_request.conflicts,
            )
            async with dbaccess.Query[int](
                cursor,
                """SELECT id
                     FROM highlightfiles
                    WHERE repository={repository_id}
                      AND sha1={sha1}
                      AND language={language_id}
                      AND conflicts={conflicts}""",
                repository_id=highlight_request.repository_id,
                sha1=highlight_request.sha1,
                language_id=highlight_request.language_id,
                conflicts=highlight_request.conflicts,
            ) as result:
                file_id = await result.scalar()
            await cursor.execute(
                """UPDATE highlightfiles
                      SET highlighted=TRUE,
                          requested=FALSE
                    WHERE id={file_id}""",
                file_id=file_id,
            )
            await cursor.execute(
                """DELETE
                     FROM highlightlines
                    WHERE file={file_id}""",
                file_id=file_id,
            )
            await cursor.executemany(
                """INSERT
                     INTO highlightlines (
                            file, line, data
                          ) VALUES (
                            {file_id}, {index}, {data}
                          )""",
                [
                    dbaccess.parameters(file_id=file_id, index=index, data=data)
                    for index, data in enumerate(lines)
                ],
            )
            await cursor.execute(
                """DELETE
                     FROM codecontexts
                    WHERE sha1={sha1}
                      AND language={language_id}""",
                sha1=highlight_request.sha1,
                language_id=highlight_request.language_id,
            )
            await cursor.executemany(
                """INSERT INTO codecontexts (
                     sha1, language, first_line, last_line, context
                   ) VALUES (
                     {sha1}, {language_id}, {first_line}, {last_line}, {context}
                   )""",
                (
                    dbaccess.parameters(
                        sha1=highlight_request.sha1,
                        language_id=highlight_request.language_id,
                        first_line=first_line,
                        last_line=last_line,
                        context=context,
                    )
                    for first_line, last_line, context in contexts
                ),
            )

    return SyntaxHighlighFile.Response(file_id)


async def handle_analyzechangedlines(
    loop: asyncio.AbstractEventLoop, request: pubsub.IncomingRequest
) -> AnalyzeChangedLines.Response:
    from critic.diff.analyze import analyzeChunk

    payload = cast(object, request.payload)

    assert isinstance(payload, AnalyzeChangedLines.Request)

    old_lines = payload.old_lines
    new_lines = payload.new_lines

    logger.debug("%s: handle_analyzechangedlines", request.request_id)

    analysis = await loop.run_in_executor(None, analyzeChunk, old_lines, new_lines)

    if analysis is None:
        logger.debug("%s: no analysis: %r %r", request.request_id, old_lines, new_lines)
    else:
        logger.debug("%s: analysis: %r", request.request_id, analysis)

    return AnalyzeChangedLines.Response(analysis)


Callback = Callable[[asyncio.AbstractEventLoop, pubsub.IncomingRequest], Any]


class Handler:
    async def __call__(
        self,
        callback: Callback,
        channel_name: pubsub.ChannelName,
        request: pubsub.IncomingRequest,
    ) -> None:
        logger.debug(
            "%s: handle_request: channel_name=%r", request.request_id, channel_name
        )

        await request.notify_delivery()

        try:
            response = await callback(asyncio.get_running_loop(), request)
        except Error as error:
            await request.notify_error(str(error))
        else:
            await request.notify_response(response)


def setup(parser: argparse.ArgumentParser) -> None:
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
                    channel_name,
                    functools.partial(handler, callback),
                )
            await stopped.wait()
    except Exception:
        logger.exception("Failed to connect to PubSub and subscribe to channels!")
        stopped.set()


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
