from __future__ import annotations

import asyncio
import logging
import logging.handlers
import pickle
import struct
import traceback
from queue import Queue
from threading import Thread
from typing import AsyncIterable, BinaryIO, Optional, TypedDict, Union


HEADER_FMT = "!I"


class LogRecord(TypedDict):
    level: int
    name: str
    message: str
    traceback: Optional[str]


def _write(stream: BinaryIO, queue: Queue[Union[logging.LogRecord, dict]]) -> None:
    while item := queue.get():
        if isinstance(item, logging.LogRecord):
            reduced = {
                "log": {
                    "level": item.levelno,
                    "name": item.name,
                    "message": (item.msg % item.args if item.args else item.msg),
                    "traceback": (
                        "".join(traceback.format_exception(*item.exc_info))
                        if item.exc_info
                        else None
                    ),
                }
            }
        else:
            reduced = item
        data = pickle.dumps(reduced)
        try:
            stream.write(struct.pack(HEADER_FMT, len(data)) + data)
            stream.flush()
        except ConnectionError:
            break


class BinaryHandler(logging.handlers.QueueHandler):
    queue: Queue[Union[logging.LogRecord, dict]]

    def __init__(self, stream: BinaryIO):
        self.queue = Queue()
        super().__init__(self.queue)
        Thread(target=_write, args=(stream, self.queue), daemon=True).start()

    def write(self, item: dict) -> None:
        self.queue.put(item)


def emit(record: dict, *, suffix: str = None) -> None:
    name = record["name"]
    if suffix:
        name += f":{suffix}"
    logging.getLogger(name).log(record["level"], record["message"])


async def read(reader: Optional[asyncio.StreamReader]) -> AsyncIterable[object]:
    assert reader
    while True:
        try:
            header = await reader.readexactly(struct.calcsize(HEADER_FMT))
        except asyncio.IncompleteReadError as error:
            assert not error.partial
            break
        data_len: int = struct.unpack(HEADER_FMT, header)[0]
        yield pickle.loads(await reader.readexactly(data_len))
