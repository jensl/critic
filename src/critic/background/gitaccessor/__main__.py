# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 Jens Lindström, Opera Software ASA
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
import os
import traceback
from typing import (
    Any,
    AsyncIterable,
    AsyncIterator,
    Dict,
    Literal,
    Optional,
    Sequence,
    TypedDict,
    Union,
    cast,
)

logger = logging.getLogger("critic.background.gitaccessor")

from critic import background
from critic import gitaccess

from ..service import BackgroundService, call
from ..binaryprotocol import BinaryProtocolClient, BinaryProtocol
from .protocol import (
    FetchRequest,
    FetchObject,
    FetchError,
    FetchResponse,
    FetchRangeRequest,
    FetchRangeObject,
    FetchRangeEnd,
    FetchRangeError,
    FetchRangeResponse,
    CallRequest,
    CallResult,
    CallError,
    CallResponse,
    StreamRequest,
    StreamInput,
    StreamOutput,
    StreamEnd,
    StreamError,
    StreamResponse,
    InputMessage,
    OutputMessage,
)


class GitAccessorClient(BinaryProtocolClient[InputMessage, OutputMessage]):
    pass


class GitAccessorService(
    BackgroundService, BinaryProtocol[GitAccessorClient, InputMessage, OutputMessage]
):
    name = "gitaccessor"

    GENERIC_COMMANDS = {
        "version",
        "repositories_dir",
        "symbolicref",
        "revlist",
        "revparse",
        "mergebase",
        "lstree",
        "foreachref",
        "updateref",
        "lsremote",
    }

    repositories: Dict[Optional[str], gitaccess.GitRepository]
    streams: Dict[int, "asyncio.Queue[bytes]"]

    def __init__(self) -> None:
        super().__init__()
        self.repositories = {}
        self.streams = {}

    def get_repository(self, path: Optional[str]) -> gitaccess.GitRepository:
        if path not in self.repositories:
            self.repositories[path] = gitaccess.GitRepository.direct(path)
        return self.repositories[path]

    async def did_start(self) -> None:
        repository = self.get_repository(None)
        assert repository
        logger.info("Git version: %s", await repository.version())

    def handle_connection(self) -> asyncio.StreamReaderProtocol:
        return BinaryProtocol.handle_connection(self)

    def create_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> GitAccessorClient:
        return GitAccessorClient(reader, writer)

    def client_connected(self, client: GitAccessorClient) -> None:
        logger.debug("client connected")

    def client_disconnected(self, client: GitAccessorClient) -> None:
        logger.debug("client disconnected")

    async def dispatch_message(
        self, client: GitAccessorClient, message: InputMessage
    ) -> AsyncIterator[OutputMessage]:
        response: Optional[AsyncIterable[OutputMessage]] = None

        # logger.debug("incoming message: %r", message)

        if isinstance(message, StreamInput):
            try:
                queue = self.streams[message.request_id]
            except KeyError:
                yield StreamError(
                    message.request_id, gitaccess.GitError(f"invalid stream")
                )
            else:
                await queue.put(message.data)
            return

        try:
            repository = self.get_repository(message.repository_path)

            if isinstance(message, FetchRequest):
                response = self.handle_fetch(repository, message)
            elif isinstance(message, FetchRangeRequest):
                response = self.handle_fetchrange(repository, message)
            elif isinstance(message, CallRequest):
                response = self.handle_call(repository, message)
            elif isinstance(message, StreamRequest):
                response = self.handle_stream(repository, message)
            else:
                raise Exception("Invalid message: request=%r" % message["request"])

            async for output_message in response:
                yield output_message
        except gitaccess.GitError as error:
            yield message.error(error, traceback.format_exc())

    async def handle_fetch(
        self, repository: gitaccess.GitRepository, request: FetchRequest
    ) -> AsyncIterable[FetchResponse]:
        async for object_id, raw_object in repository.fetch(*request.object_ids):
            if isinstance(raw_object, gitaccess.GitFetchError):
                logger.warning(raw_object)
                yield request.error(raw_object, "", object_id)
            else:
                assert isinstance(raw_object, gitaccess.GitRawObject)
                yield request.response(object_id, raw_object)

    async def handle_fetchrange(
        self, repository: gitaccess.GitRepository, request: FetchRangeRequest
    ) -> AsyncIterator[FetchRangeResponse]:
        async for object_id, raw_object in repository.fetch(
            include=request.include,
            exclude=request.exclude,
            order=request.order,
            skip=request.skip,
            limit=request.limit,
            object_factory=gitaccess.GitRawObject,
        ):
            assert isinstance(raw_object, gitaccess.GitRawObject)
            yield request.response_object(raw_object)
        yield request.response_end()

    async def handle_call(
        self, repository: gitaccess.GitRepository, request: CallRequest,
    ) -> AsyncIterator[CallResponse]:
        yield request.response(
            await (getattr(repository, request.call))(*request.args, **request.kwargs)
        )

    async def handle_stream(
        self, repository: gitaccess.GitRepository, request: StreamRequest
    ) -> AsyncIterator[StreamResponse]:
        input_queue: "asyncio.Queue[bytes]" = asyncio.Queue()
        output_queue: "asyncio.Queue[bytes]" = asyncio.Queue()

        self.streams[request.request_id] = input_queue

        future = asyncio.ensure_future(
            repository.stream(request.command, input_queue, output_queue, request.env)
        )

        while True:
            data = await output_queue.get()
            yield request.response_output(data)
            if not data:
                break

        await future
        yield request.response_end()


if __name__ == "__main__":
    call(GitAccessorService)
