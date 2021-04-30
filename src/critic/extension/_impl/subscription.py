from contextlib import asynccontextmanager
from dataclasses import dataclass
from traceback import format_exc
from typing import AsyncIterator

from critic.protocol.extensionhost import (
    CallError,
    SubscriptionMessage,
    SubscriptionResponseItem,
)
from critic.extension.subscription import MessageHandle

from . import Runner, WriteResponse
from .. import Message


@dataclass
class MessageImpl:
    __channel: str
    __payload: object

    @property
    def channel(self) -> str:
        return self.__channel

    @property
    def payload(self) -> object:
        return self.__payload


@asynccontextmanager
async def message_handle(
    message: SubscriptionMessage, write_response: WriteResponse
) -> AsyncIterator[Message]:
    try:
        yield MessageImpl(message.channel, message.payload)
    except Exception as error:
        await write_response(SubscriptionResponseItem(CallError.from_exception(error)))
    else:
        await write_response(SubscriptionResponseItem(None))


class SubscriptionImpl(Runner):
    @property
    async def messages(self) -> AsyncIterator[MessageHandle]:
        async for command, write_response in self.commands():
            assert isinstance(command, SubscriptionMessage)
            yield message_handle(command, write_response)
