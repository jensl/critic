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
import threading
import uuid
from collections import defaultdict
from types import TracebackType
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
    FrozenSet,
    cast,
)

logger = logging.getLogger(__name__)

from critic import background
from critic.background.utils import is_services
from critic.gitaccess import (
    FetchJob,
    FetchRangeOrder,
    GitError,
    GitFetchError,
    GitObject,
    GitRawObject,
    GitRepository,
    GitRepositoryImpl,
    ObjectType,
    resolve_object_factory,
    SHA1,
    StreamCommand,
)

from .protocol import (
    Call,
    CallError,
    CallRequest,
    CallResult,
    FetchError,
    FetchObject,
    FetchRangeError,
    FetchRangeObject,
    FetchRangeRequest,
    FetchRequest,
    InputMessage,
    OutputMessage,
    RequestId,
    StreamEnd,
    StreamError,
    StreamInput,
    StreamOutput,
    StreamRequest,
)
from ..messagechannel import MessageChannel


class GitObjectCache:
    __instance: Optional[GitObjectCache] = None
    __objects: Dict[SHA1, GitRawObject]

    @staticmethod
    def instance() -> GitObjectCache:
        if GitObjectCache.__instance is None:
            GitObjectCache.__instance = GitObjectCache()
        return GitObjectCache.__instance

    def __init__(self) -> None:
        self.__lock = threading.Lock()
        self.__objects = {}

    def lookup(
        self, object_ids: Iterable[SHA1]
    ) -> Tuple[Dict[SHA1, GitRawObject], List[SHA1]]:
        cached: Dict[SHA1, GitRawObject] = {}
        not_cached: List[SHA1] = []
        for object_id in object_ids:
            try:
                cached[object_id] = self.__objects[object_id]
            except KeyError:
                not_cached.append(object_id)
        return cached, not_cached

    def update(self, updates: Dict[SHA1, GitRawObject]) -> None:
        self.__objects.update(updates)

    def __enter__(self) -> GitObjectCache:
        self.__lock.acquire()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Optional[bool]:
        self.__lock.release()
        return None


class GitProxyError(GitError):
    def __init__(
        self,
        message: str = None,
        exception: BaseException = None,
        stacktrace: TracebackType = None,
        stderr: bytes = None,
    ):
        super().__init__(message or (str(exception) if exception else "unknown error"))
        self.exception = exception
        self.stacktrace = stacktrace
        self.stderr = stderr


GenericCommand = Literal[
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
]

GENERIC_COMMANDS: FrozenSet[GenericCommand] = frozenset(
    {
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
)


class GitRepositoryProxy(GitRepositoryImpl):
    fetch_requests: Dict[SHA1, List[FetchJob]]
    fetchrange_requests: Dict[RequestId, "asyncio.Queue[Optional[GitRawObject]]"]
    generic_requests: Dict[RequestId, asyncio.Future]
    streams: Dict[RequestId, Tuple["asyncio.Queue[bytes]", "asyncio.Future[None]"]]

    def __init__(self, path: Optional[str]) -> None:
        self.__path = path
        self.fetch_requests = defaultdict(list)
        self.fetchrange_requests = {}
        self.generic_requests = {}
        self.request_id_counter = 0
        self.streams = {}
        self.channel = MessageChannel[InputMessage, OutputMessage](
            "gitaccessor", dispatch_message=self.dispatch_message
        )

        # Uncomment this line to debug proxy issues.
        # asyncio.ensure_future(self.debug(), loop=self.loop)

    @property
    def path(self) -> Optional[str]:
        return self.__path

    async def write_message(self, message: InputMessage) -> None:
        await self.channel.write_message(message)

    async def debug(self) -> None:
        while True:
            await asyncio.sleep(5)
            if self.fetch_requests:
                logger.debug(
                    "%r: %d pending fetch requests:", self, len(self.fetch_requests)
                )
                for object_id in self.fetch_requests.keys():
                    logger.debug("  %r", object_id)

    def __request_id(self) -> RequestId:
        self.request_id_counter += 1
        return RequestId(self.request_id_counter)

    async def __generic(self, call: Call, args: tuple = (), kwargs: dict = {}) -> Any:
        assert self.path
        request = CallRequest(self.__request_id(), self.path, call, args, kwargs)
        self.generic_requests[
            request.request_id
        ] = future = asyncio.get_running_loop().create_future()
        await self.write_message(request)
        return await future

    async def version(self) -> str:
        return await self.__generic("version")

    # async def repositories_dir(self) -> str:
    #     return await self.__generic("repositories_dir")

    async def fetch(
        self,
        *object_ids: SHA1,
        include: Optional[Iterable[str]],
        exclude: Optional[Iterable[str]],
        order: FetchRangeOrder,
        skip: Optional[int],
        limit: Optional[int],
        wanted_object_type: Optional[ObjectType],
        object_factory: Optional[Type[GitObject]],
    ) -> AsyncIterator[Tuple[SHA1, Union[GitObject, GitFetchError]]]:
        assert self.path
        if object_factory is None:
            object_factory = resolve_object_factory(wanted_object_type)
        if include is not None:
            request_id = self.__request_id()
            queue: "asyncio.Queue[Optional[GitRawObject]]"
            queue = self.fetchrange_requests[request_id] = asyncio.Queue()
            await self.write_message(
                FetchRangeRequest(
                    request_id,
                    self.path,
                    list(include),
                    list(exclude) if exclude else [],
                    order,
                    skip,
                    limit,
                )
            )
            while True:
                raw_object = await queue.get()
                if raw_object is None:
                    break
                yield raw_object.sha1, object_factory.fromRawObject(raw_object)
            del self.fetchrange_requests[request_id]
            return
        with GitObjectCache.instance() as cache:
            cached, not_cached = cache.lookup(object_ids)
        for object_id, raw_object in cached.items():
            yield object_id, object_factory.fromRawObject(raw_object)
        if not not_cached:
            return
        jobs = {}
        not_requested = []
        for object_id in not_cached:
            job = FetchJob(
                object_id,
                wanted_object_type=wanted_object_type,
                object_factory=object_factory,
            )
            jobs[job.future] = job
            if object_id not in self.fetch_requests:
                not_requested.append(object_id)
            self.fetch_requests[object_id].append(job)
        if not_requested:
            await self.write_message(
                FetchRequest(self.__request_id(), self.path, not_requested)
            )
        futures = set(jobs.keys())
        cache_updates = {}
        while futures:
            done, futures = await asyncio.wait(
                futures, return_when=asyncio.FIRST_COMPLETED, timeout=1
            )
            for future in done:
                job = jobs[future]
                assert job.object_id
                raw_object = cast(GitRawObject, future.result())
                cache_updates[job.object_id] = raw_object
                if job.object_id != raw_object.sha1:
                    cache_updates[raw_object.sha1] = raw_object
                yield job.object_id, job.object_factory.fromRawObject(raw_object)
        with GitObjectCache.instance() as cache:
            cache.update(cache_updates)

    async def symbolicref(self, *args: Any, **kwargs: Any) -> Any:
        return await self.__generic("symbolicref", args, kwargs)

    async def revparse(self, *args: Any, **kwargs: Any) -> Any:
        return await self.__generic("revparse", args, kwargs)

    async def revlist(self, *args: Any, **kwargs: Any) -> Any:
        return await self.__generic("revlist", args, kwargs)

    async def mergebase(self, *args: Any, **kwargs: Any) -> Any:
        return await self.__generic("mergebase", args, kwargs)

    async def lstree(self, *args: Any, **kwargs: Any) -> Any:
        return await self.__generic("lstree", args, kwargs)

    async def foreachref(self, *args: Any, **kwargs: Any) -> Any:
        return await self.__generic("foreachref", args, kwargs)

    async def updateref(self, *args: Any, **kwargs: Any) -> Any:
        await self.__generic("updateref", args, kwargs)

    async def lsremote(self, *args: Any, **kwargs: Any) -> Any:
        return await self.__generic("lsremote", args, kwargs)

    async def stream(
        self,
        command: StreamCommand,
        input_queue: "asyncio.Queue[bytes]",
        output_queue: "asyncio.Queue[bytes]",
        env: Optional[Mapping[str, str]],
    ) -> None:
        assert self.path

        request_id = self.__request_id()
        future = asyncio.get_running_loop().create_future()

        self.streams[request_id] = (output_queue, future)

        await self.write_message(
            StreamRequest(request_id, self.path, command, env or {})
        )

        async def handle_input() -> None:
            while True:
                data = await input_queue.get()
                await self.write_message(StreamInput(request_id, data))
                if not data:
                    break

        await asyncio.gather(handle_input(), future)

    async def dispatch_message(self, message: Optional[OutputMessage]) -> None:
        try:
            await self.__dispatch_message(message)
        except Exception:
            logger.exception("Crash in message dispatch!")

    async def __dispatch_message(self, message: Optional[OutputMessage]) -> None:
        def make_raw_object() -> GitRawObject:
            assert isinstance(message, (FetchObject, FetchRangeObject))
            return GitRawObject(
                sha1=message.sha1, object_type=message.object_type, data=message.data
            )

        def handle_error(future: asyncio.Future) -> None:
            assert isinstance(
                message, (FetchError, FetchRangeError, CallError, StreamError)
            )
            future.set_exception(message.exception)

        if isinstance(message, FetchObject):
            jobs = self.fetch_requests.pop(message.object_id, None)
            if jobs is None:
                logger.warning(
                    "%r: received unexpected fetch response for: %r",
                    self,
                    message.object_id,
                )
                return
            raw_object = make_raw_object()
            for job in jobs:
                job.future.set_result(raw_object)
        elif isinstance(message, FetchRangeObject):
            queue = self.fetchrange_requests[message.request_id]
            await queue.put(make_raw_object())
        elif isinstance(message, CallResult):
            future = self.generic_requests.pop(message.request_id, None)
            if future is None:
                return
            future.set_result(message.result)
        elif isinstance(message, CallError):
            future = self.generic_requests.pop(message.request_id, None)
            if future is None:
                return
            future.set_exception(message.exception)
        elif isinstance(message, StreamOutput):
            output_queue, future = self.streams[message.request_id]
            assert not future.done()
            await output_queue.put(message.data)
        elif isinstance(message, StreamEnd):
            output_queue, future = self.streams[message.request_id]
            assert not future.done()
            future.set_result(None)
        else:
            raise Exception("Invalid message: %r" % message)

    async def channel_closed(self) -> None:
        error = GitProxyError("Channel closed prematurely")
        for jobs in self.fetch_requests.values():
            for job in jobs:
                job.future.set_exception(error)
        self.fetch_requests.clear()
        for future in self.generic_requests.values():
            future.set_exception(error)
        self.generic_requests.clear()

    async def close(self) -> None:
        await self.channel.close()

    @staticmethod
    def make(path: str = None) -> GitRepository:
        if is_services():
            return GitRepository.direct(path)
        return GitRepository(GitRepositoryProxy(path))
