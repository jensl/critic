from __future__ import annotations

import aiohttp
import contextlib
import logging
import pytest
from typing import Any, Dict, AsyncIterator, Literal, Optional, TypeVar, Union

from .instance import Instance, User
from ..utilities import AccessToken, Anonymizer, raise_for_status

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FrontendError(Exception):
    def __init__(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, Any]],
        payload: Any,
        status_code: int,
        body: Any,
    ):
        self.method = method
        self.path = path
        self.query = query
        self.payload = payload
        self.status_code = status_code
        self.body = body


class FrontendResponse:
    def __init__(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, Any]],
        request_body: Optional[Union[bytes, str]],
        status_code: int,
        content_type: Optional[str],
        response_body: Optional[str],
    ):
        self.method = method
        self.path = path
        self.query = query
        self.request_body = request_body
        self.status_code = status_code
        self.content_type = content_type
        self.response_body = response_body

    @staticmethod
    async def make(
        method: str,
        path: str,
        query: Optional[Dict[str, Any]],
        request_body: Optional[Union[bytes, str]] = None,
        *,
        response: aiohttp.ClientResponse,
    ) -> FrontendResponse:
        return FrontendResponse(
            method,
            path,
            query,
            request_body,
            response.status,
            response.content_type,
            await response.text(),
        )

    def raise_for_status(self) -> FrontendResponse:
        if self.status_code >= 400:
            raise FrontendError(
                self.method,
                self.path,
                self.query,
                self.request_body,
                self.status_code,
                self.response_body,
            )
        return self

    def to_json(self) -> dict[Any, Any]:
        request: Dict[str, Any] = dict(method=self.method, path=self.path)
        if self.query:
            request["query"] = self.query
        if self.request_body is not None:
            request["body"] = self.request_body
        return dict(
            request=request,
            response=dict(
                status_code=self.status_code,
                content_type=self.content_type,
                body=self.response_body,
            ),
        )

    @staticmethod
    def from_json(value: dict[Any, Any]) -> FrontendResponse:
        return FrontendResponse(
            value["request"]["method"],
            value["request"]["path"],
            value["request"].get("query", {}),
            request_body=value["request"].get("body"),
            status_code=value["response"]["status_code"],
            content_type=value["response"].get("content_type"),
            response_body=value["response"].get("body"),
        )


class Frontend:
    def __init__(
        self, instance: Instance, anonymizer: Anonymizer, session: aiohttp.ClientSession
    ):
        self.__instance = instance
        self.__anonymizer = anonymizer
        self.__client_session = session
        self.__address = instance.address
        self.__prefix = f"http://{self.__address[0]}:{self.__address[1]}"

    @property
    def instance(self) -> Instance:
        return self.__instance

    @property
    def anonymizer(self) -> Instance:
        return self.__instance

    @property
    def client_session(self) -> aiohttp.ClientSession:
        return self.__client_session

    @property
    def prefix(self) -> str:
        return self.__prefix

    @property
    def port(self) -> int:
        return self.__address[1]

    async def get(
        self,
        path: str,
        *,
        params: Dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> FrontendResponse:
        async with self.__client_session.get(
            f"{self.__prefix}/{path}", params=params, headers=headers
        ) as response:
            return await FrontendResponse.make("GET", path, params, response=response)

    async def post(
        self,
        path: str,
        body: Union[bytes, str],
        *,
        params: Dict[str, Any],
        headers=None,
    ) -> FrontendResponse:
        async with self.__client_session.post(
            f"{self.__prefix}/{path}", data=body, params=params, headers=headers
        ) as response:
            return await FrontendResponse.make(
                "POST", path, params, body, response=response
            )

    async def put(
        self,
        path: str,
        body: Union[bytes, str],
        *,
        params: Dict[str, Any],
        headers=None,
    ) -> FrontendResponse:
        async with self.__client_session.put(
            f"{self.__prefix}/{path}", data=body, params=params, headers=headers
        ) as response:
            return await FrontendResponse.make(
                "PUT", path, params, body, response=response
            )

    async def delete(
        self, path: str, *, params: Dict[str, Any], headers=None
    ) -> FrontendResponse:
        async with self.__client_session.delete(
            f"{self.__prefix}/{path}", params=params, headers=headers
        ) as response:
            return await FrontendResponse.make(
                "DELETE", path, params, response=response
            )

    @contextlib.asynccontextmanager
    async def session(
        self,
        user: Union[User, AccessToken],
        *,
        session_type: Literal["cookie", "httpauth"] = None,
    ) -> AsyncIterator[Frontend]:
        from .api import API

        auth: Optional[aiohttp.BasicAuth] = None
        cookie_jar: aiohttp.abc.AbstractCookieJar
        headers: Optional[dict] = None

        if session_type == "httpauth" or (
            session_type is None and isinstance(user, AccessToken)
        ):
            cookie_jar = aiohttp.DummyCookieJar()
            if isinstance(user, AccessToken):
                headers = {"Authorization": f"Bearer {user.value}"}
            else:
                auth = aiohttp.BasicAuth(user.name, user.password)
        else:
            cookie_jar = aiohttp.CookieJar(unsafe=True)

        async with aiohttp.ClientSession(
            auth=auth, cookie_jar=cookie_jar, headers=headers
        ) as session:
            frontend = Frontend(self.__instance, self.__anonymizer, session)
            if isinstance(user, User):
                api = API(frontend, self.__anonymizer)
                raise_for_status(
                    await api.post(
                        "sessions", {"username": user.name, "password": user.password}
                    )
                )
                for cookie in cookie_jar:
                    if cookie.key == "sid":
                        self.__anonymizer.replace_string(
                            cookie.value, f"SessionCookie({user.name})"
                        )
                try:
                    yield frontend
                finally:
                    raise_for_status(await api.delete("sessions/current"))
            else:
                yield frontend


@pytest.fixture
async def frontend(
    instance: Instance, anonymizer: Anonymizer
) -> AsyncIterator[Frontend]:
    async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as session:
        frontend = Frontend(instance, anonymizer, session)
        anonymizer.replace_string(frontend.prefix, "http://critic.example.org")
        anonymizer.replace_string(f"0.0.0.0:{frontend.port}", "critic.example.org")
        yield frontend
