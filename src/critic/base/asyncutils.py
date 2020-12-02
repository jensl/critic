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

import asyncio
import logging
import os
from typing import Any, Awaitable, BinaryIO, Collection, TextIO, Type, TypeVar, Union

logger = logging.getLogger(__name__)


def contextmanager(fn):
    def wrapper(*args, **kwargs):
        class ContextManager:
            async def __aenter__(self):
                self.generator = fn(*args, **kwargs)
                assert self.generator.__aiter__() is self.generator
                try:
                    return await self.generator.__anext__()
                except StopAsyncIteration:
                    raise Exception(
                        "invalid context manager function: " "never yielded"
                    )

            async def __aexit__(self, exc_type, exc, tb):
                try:
                    if exc_type is None:
                        await self.generator.__anext__()
                    else:
                        await self.generator.athrow(exc_type, exc, tb)
                except StopAsyncIteration:
                    return True
                else:
                    raise Exception(
                        "invalid context manager function: " "yielded more than once"
                    )

        return ContextManager()

    return wrapper


def serialized(fn):
    assert asyncio.iscoroutinefunction(fn)
    lock = asyncio.Lock()

    async def wrapper(*args, **kwargs):
        await lock.acquire()
        try:
            return await fn(*args, **kwargs)
        finally:
            lock.release()

    return wrapper


T = TypeVar("T")


async def gather(
    *coros_or_futures: Awaitable[T],
    return_exceptions: bool = False,
    silent_exceptions: Collection[Type[BaseException]] = (),
):
    """Like asyncio.gather(), but cancels remaining pending futures"""

    if not coros_or_futures:
        return []
    futures = [
        asyncio.ensure_future(coro_or_future) for coro_or_future in coros_or_futures
    ]
    if return_exceptions:
        return_when = asyncio.ALL_COMPLETED
    else:
        return_when = asyncio.FIRST_EXCEPTION
    done, pending = await asyncio.wait(futures, return_when=return_when)
    try:
        return [future.result() for future in futures if future in done]
    except Exception:
        for future in done:
            try:
                future.result()
            except silent_exceptions:  # type: ignore
                pass
            except Exception:
                logger.exception("Coroutine failed!")
        for future in pending:
            future.cancel()
        raise


async def create_reader(
    source: Union[int, BinaryIO, TextIO], /, *, limit: int = 65536
) -> asyncio.StreamReader:
    reader = asyncio.StreamReader(limit=limit)
    if isinstance(source, int):
        source = os.fdopen(source, "rb")
    await asyncio.get_running_loop().connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), source
    )
    return reader


async def create_writer(source: Union[int, BinaryIO]) -> asyncio.StreamWriter:
    loop = asyncio.get_running_loop()
    if isinstance(source, int):
        source = os.fdopen(source, "wb")
    writer_transport, writer_protocol = await loop.connect_write_pipe(
        lambda: asyncio.streams.FlowControlMixin(), source
    )
    return asyncio.streams.StreamWriter(writer_transport, writer_protocol, None, loop)
