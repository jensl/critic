from __future__ import annotations
from contextlib import asynccontextmanager

from types import TracebackType
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterator,
    Dict,
    Literal,
    Optional,
    Protocol,
    Type,
    Union,
)
from multidict import CIMultiDict, CIMultiDictProxy, MultiDictProxy

from critic import api


class Response(Protocol):
    @property
    def headers(self) -> CIMultiDictProxy:
        ...

    async def write(self, data: Union[bytes, str]) -> None:
        ...


class Request(Protocol):
    @property
    def method(self) -> Literal["GET", "PATCH", "POST", "PUT", "DELETE"]:
        ...

    @property
    def path(self) -> str:
        ...

    @property
    def query(self) -> MultiDictProxy:
        ...

    @property
    def headers(self) -> CIMultiDictProxy:
        ...

    @property
    async def has_body(self) -> bool:
        ...

    async def read(self) -> bytes:
        ...

    async def text(self) -> str:
        ...

    async def json(self) -> object:
        ...

    def response(
        self,
        status_code: int,
        status_text: str = None,
        /,
        headers: Dict[str, str] = None,
    ) -> AsyncContextManager[Response]:
        ...


class Endpoint(Protocol):
    @property
    def critic(self) -> api.critic.Critic:
        ...

    @property
    def requests(self) -> AsyncIterator[Request]:
        ...
