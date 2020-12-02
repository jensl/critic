from __future__ import annotations

import http
from typing import (
    AsyncContextManager,
    AsyncIterator,
    ClassVar,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Union,
)
from multidict import CIMultiDictProxy, MultiDictProxy

from critic import api


class HTTPResponse(Exception):
    headers: Mapping[str, str]

    def __init__(
        self,
        status_code: int,
        status_text: Optional[str] = None,
        /,
        *,
        body: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
    ):
        self.status_code = status_code
        self.status_text = status_text or http.HTTPStatus(status_code).phrase
        self.body = body
        self.headers = headers or {"content-type": "text/plain"}


class HTTPNoContent(HTTPResponse):
    def __init__(self) -> None:
        super().__init__(http.HTTPStatus.NO_CONTENT)


class HTTPError(HTTPResponse):
    __status_code: ClassVar[int]

    def __init_subclass__(cls, *, status_code: int) -> None:
        cls.__status_code = status_code

    def __init__(self, body: str, *, headers: Optional[Mapping[str, str]] = None):
        super().__init__(self.__status_code, body=body, headers=headers)


class HTTPNotFound(HTTPError, status_code=http.HTTPStatus.NOT_FOUND):
    pass


class HTTPBadRequest(HTTPError, status_code=http.HTTPStatus.BAD_REQUEST):
    pass


class HTTPForbidden(HTTPError, status_code=http.HTTPStatus.FORBIDDEN):
    pass


class Response(Protocol):
    @property
    def headers(self) -> CIMultiDictProxy[str]:
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
    def query(self) -> MultiDictProxy[str]:
        ...

    @property
    def headers(self) -> CIMultiDictProxy[str]:
        ...

    @property
    def has_body(self) -> bool:
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
        status_text: Optional[str] = None,
        /,
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncContextManager[Response]:
        ...

    async def json_response(
        self, status_code: int = 200, /, *, payload: object
    ) -> None:
        ...


class RequestHandle(AsyncContextManager[Request], Protocol):
    ...


class Endpoint(Protocol):
    @property
    def critic(self) -> api.critic.Critic:
        ...

    @property
    def requests(self) -> AsyncIterator[RequestHandle]:
        ...
