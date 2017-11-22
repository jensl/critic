from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from critic.background.extensionhost import (
    SubscriptionMessage,
    SubscriptionResponseItem,
)
from critic.extension.subscription import MessageHandle

from . import Runner, WriteResponse
from .. import Message


@dataclass
class MessageImpl:
    channel: str
    payload: object


@asynccontextmanager
async def message_handle(
    message: SubscriptionMessage, write_response: WriteResponse
) -> AsyncIterator[Message]:
    try:
        yield MessageImpl(message.channel, message.payload)
    except Exception as error:
        await write_response(SubscriptionResponseItem(message.request_id, str(error)))
    else:
        await write_response(SubscriptionResponseItem(message.request_id))


class SubscriptionImpl(Runner):
    @property
    async def messages(self) -> AsyncIterator[MessageHandle]:
        async for command, write_response in self.commands(
            self.critic, self.stdin, self.stdout
        ):
            assert isinstance(command, SubscriptionMessage)
            yield message_handle(command, write_response)
