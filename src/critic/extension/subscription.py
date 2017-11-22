from __future__ import annotations

from types import TracebackType
from typing import (
    AsyncContextManager,
    AsyncIterator,
    Awaitable,
    Optional,
    Protocol,
    Type,
)

from critic import api


class Message(Protocol):
    @property
    def channel(self) -> str:
        ...

    @property
    def payload(self) -> object:
        ...


class MessageHandle(Protocol):
    def __aenter__(self) -> Awaitable[Message]:
        ...

    def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Awaitable[Optional[bool]]:
        ...


class Subscription(Protocol):
    @property
    def critic(self) -> api.critic.Critic:
        ...

    @property
    def messages(self) -> AsyncIterator[MessageHandle]:
        ...
