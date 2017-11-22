import http
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from multidict import CIMultiDict, CIMultiDictProxy, MultiDict, MultiDictProxy
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Literal,
    Mapping,
    Optional,
    Union,
)

from critic.background.extensionhost import (
    EndpointRequest,
    EndpointResponsePrologue,
    EndpointResponseBodyFragment,
    EndpointResponseEnd,
)

from . import Runner, WriteResponse
from .. import Request, Response


@dataclass
class ResponseImpl:
    write_body_fragment: Callable[[bytes], Coroutine[Any, Any, None]]

    @property
    def headers(self) -> CIMultiDictProxy:
        ...

    async def write(self, data: Union[bytes, str]) -> None:
        if isinstance(data, str):
            data = data.encode()
        await self.write_body_fragment(data)  # type: ignore

    async def close(self) -> None:
        ...


@dataclass
class RequestImpl:
    request_id: bytes = field(repr=False)
    method: Literal["GET", "PATCH", "POST", "PUT", "DELETE"]
    path: str
    query: MultiDictProxy
    headers: CIMultiDictProxy
    raw_body: Optional[bytes]
    write_response: WriteResponse

    @property
    def has_body(self) -> bool:
        return self.raw_body is not None

    async def read(self) -> bytes:
        assert self.raw_body
        return self.raw_body

    async def text(self) -> str:
        assert self.has_body
        if not isinstance(self.raw_body, str):
            raise ValueError("body is binary data")
        return self.raw_body

    async def json(self) -> Any:
        assert self.has_body
        return json.loads(await self.text)

    @asynccontextmanager
    async def response(
        self,
        status_code: int,
        status_text: str = None,
        /,
        headers: Union[
            Mapping[str, str], CIMultiDict[str], CIMultiDictProxy[str],
        ] = {},
    ) -> AsyncIterator[Response]:
        if status_text is None:
            status_text = http.HTTPStatus(status_code).phrase

        await self.write_response(
            EndpointResponsePrologue(
                self.request_id, status_code, status_text, list(headers.items())
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


class EndpointImpl(Runner):
    @property
    async def requests(self) -> AsyncIterator[Request]:
        async for command, write_response in self.commands(
            self.critic, self.stdin, self.stdout
        ):
            assert isinstance(command, EndpointRequest)
            yield RequestImpl(
                command.request_id,
                command.method,
                command.path,
                MultiDictProxy(MultiDict(command.query)),
                CIMultiDictProxy(CIMultiDict(command.headers)),
                command.body,
                write_response,
            )
