import http
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from multidict import CIMultiDict, CIMultiDictProxy, MultiDict, MultiDictProxy
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterator,
    Callable,
    Coroutine,
    Literal,
    Mapping,
    Optional,
    Union,
)

logger = logging.getLogger(__name__)

from critic import api
from critic.background.extensionhost import (
    EndpointRequest,
    EndpointResponsePrologue,
    EndpointResponseBodyFragment,
    EndpointResponseEnd,
)

from . import Runner, WriteResponse
from ..endpoint import (
    Endpoint,
    Request,
    RequestHandle,
    Response,
    HTTPError,
    HTTPForbidden,
)


@dataclass
class ResponseImpl:
    write_body_fragment: Callable[[bytes], Coroutine[Any, Any, None]]

    @property
    def headers(self) -> CIMultiDictProxy[str]:
        ...

    async def write(self, data: Union[bytes, str]) -> None:
        if isinstance(data, str):
            data = data.encode()
        await self.write_body_fragment(data)  # type: ignore

    async def close(self) -> None:
        ...


@dataclass
class RequestImpl(Request):
    request_id: bytes = field(repr=False)
    __method: Literal["GET", "PATCH", "POST", "PUT", "DELETE"]
    __path: str
    __query: MultiDictProxy[str]
    __headers: CIMultiDictProxy[str]
    raw_body: Optional[Union[bytes, str]]
    write_response: WriteResponse

    @property
    def method(self) -> Literal["GET", "PATCH", "POST", "PUT", "DELETE"]:
        return self.__method

    @property
    def path(self) -> str:
        return self.__path

    @property
    def query(self) -> MultiDictProxy[str]:
        return self.__query

    @property
    def headers(self) -> CIMultiDictProxy[str]:
        return self.__headers

    @property
    def has_body(self) -> bool:
        return self.raw_body is not None

    async def read(self) -> bytes:
        assert self.raw_body
        if isinstance(self.raw_body, str):
            return self.raw_body.encode()
        return self.raw_body

    async def text(self) -> str:
        assert self.has_body
        if not isinstance(self.raw_body, str):
            raise ValueError("body is binary data")
        return self.raw_body

    async def json(self) -> Any:
        assert self.has_body
        return json.loads(await self.text())

    @asynccontextmanager
    async def _response(
        self,
        status_code: int,
        status_text: Optional[str],
        headers: Optional[Mapping[str, str]],
    ) -> AsyncIterator[Response]:
        if status_text is None:
            status_text = http.HTTPStatus(status_code).phrase

        await self.write_response(
            EndpointResponsePrologue(
                self.request_id,
                status_code,
                status_text,
                list(headers.items() if headers else []),
            )
        )

        async def write_body_fragment(data: bytes) -> None:
            await self.write_response(
                EndpointResponseBodyFragment(self.request_id, data)
            )

        try:
            yield ResponseImpl(write_body_fragment)
        except Exception:
            await self.write_response(EndpointResponseEnd(self.request_id, True))
        else:
            await self.write_response(EndpointResponseEnd(self.request_id))

    def response(
        self,
        status_code: int,
        status_text: Optional[str] = None,
        /,
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncContextManager[Response]:
        return self._response(status_code, status_text, headers)

    async def json_response(
        self, status_code: int = 200, /, *, payload: object
    ) -> None:
        async with self.response(
            status_code, headers={"content-type": "application/json"}
        ) as response:
            logger.debug(f"{payload=}")
            await response.write(json.dumps(payload))


@asynccontextmanager
async def request_handle(request: Request) -> AsyncIterator[Request]:
    try:
        try:
            yield request
        except api.PermissionDenied as error:
            raise HTTPForbidden(body=str(error))
    except HTTPError as error:
        async with request.response(
            error.status_code, error.status_text, headers=error.headers
        ) as response:
            await response.write(
                error.body or f"{error.status_code} {error.status_text}"
            )


class EndpointImpl(Runner, Endpoint):
    @property
    async def requests(self) -> AsyncIterator[RequestHandle]:
        async for command, write_response in self.commands():
            assert isinstance(command, EndpointRequest)
            request = RequestImpl(
                command.request_id,
                command.method,
                command.path,
                MultiDictProxy(MultiDict(command.query)),
                CIMultiDictProxy(CIMultiDict(command.headers)),
                command.body,
                write_response,
            )
            try:
                try:
                    yield request_handle(request)
                except api.PermissionDenied as error:
                    raise HTTPForbidden(body=str(error))
            except HTTPError as error:
                async with request.response(
                    error.status_code, error.status_text, headers=error.headers
                ) as response:
                    await response.write(
                        error.body or f"{error.status_code} {error.status_text}"
                    )
