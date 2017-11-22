from __future__ import annotations

import aiohttp
import contextlib
import json
import logging
import pytest
import snapshottest
from typing import (
    Any,
    Awaitable,
    Callable,
    Collection,
    Dict,
    AsyncIterator,
    Literal,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

from .frontend import Frontend, FrontendError, FrontendResponse
from .instance import User
from ..utilities import AccessToken, Anonymizer, raise_for_status

logger = logging.getLogger(__name__)

T = TypeVar("T")


class JSONResponse:
    def __init__(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, Any]],
        payload: Any,
        status_code: int,
        data: Any,
    ):
        self.method = method
        self.path = path
        self.query = query
        self.payload = payload
        self.status_code = status_code
        self.data = data

    @staticmethod
    async def make(response: FrontendResponse) -> JSONResponse:
        payload = response.request_body
        if payload is not None:
            payload = json.loads(payload)
        data = response.response_body
        if data is not None:
            try:
                data = json.loads(data)
            except Exception:
                pass
        return JSONResponse(
            response.method,
            response.path,
            response.query,
            payload,
            response.status_code,
            data,
        )

    def raise_for_status(self) -> JSONResponse:
        if self.status_code >= 400:
            raise FrontendError(
                self.method,
                self.path,
                self.query,
                self.payload,
                self.status_code,
                self.data,
            )
        return self

    def to_json(self) -> dict:
        request: Dict[str, Any] = dict(method=self.method, path=self.path)
        if self.query:
            request["query"] = self.query
        if self.payload is not None:
            request["payload"] = self.payload
        return dict(
            request=request,
            response=dict(status_code=self.status_code, data=self.data),
        )

    @staticmethod
    def from_json(value: dict) -> JSONResponse:
        return JSONResponse(
            value["request"]["method"],
            value["request"]["path"],
            value["request"].get("query", {}),
            payload=value["request"].get("payload"),
            status_code=value["response"]["status_code"],
            data=value["response"]["data"],
        )


class JSONResponseFormatter(snapshottest.formatters.BaseFormatter):
    def can_format(self, value: object) -> bool:
        return isinstance(value, JSONResponse)

    def format(self, value: JSONResponse, indent: Any, formatter: Any) -> Any:
        return snapshottest.formatters.format_dict(
            self.normalize(value, formatter), indent, formatter
        )

    def normalize(self, value: JSONResponse, formatter: Any) -> Any:
        return value.to_json()


snapshottest.formatter.Formatter.register_formatter(JSONResponseFormatter())

snapshottest.formatter.Formatter.register_formatter(
    snapshottest.formatters.TypeFormatter(type(Ellipsis), lambda v, i, f: "...")
)


class API:
    def __init__(self, frontend: Frontend, anonymizer: Anonymizer):
        self.__frontend = frontend
        self.__anonymizer = anonymizer
        self.__headers = {"Accept": "application/vnd.api+json"}

    @property
    def frontend(self) -> Frontend:
        return self.__frontend

    @staticmethod
    def processed_query(query: Dict[str, Any]) -> Dict[str, Any]:
        if "include" in query and not isinstance(query["include"], str):
            query["include"] = ",".join(query["include"])
        query.setdefault("output_format", "static")
        return {key: value for key, value in query.items() if value is not None}

    async def get(self, path: str, **query: Any) -> JSONResponse:
        path = f"api/v1/{path}"
        return await JSONResponse.make(
            await self.__frontend.get(
                path, params=API.processed_query(query), headers=self.__headers
            )
        )

    async def post(self, path: str, payload: Any, **query: Any) -> JSONResponse:
        path = f"api/v1/{path}"
        return await JSONResponse.make(
            await self.__frontend.post(
                path,
                json.dumps(payload),
                params=API.processed_query(query),
                headers=self.__headers,
            ),
        )

    async def put(self, path: str, payload: Any, **query: Any) -> JSONResponse:
        path = f"api/v1/{path}"
        return await JSONResponse.make(
            await self.__frontend.put(
                path,
                json.dumps(payload),
                params=API.processed_query(query),
                headers=self.__headers,
            ),
        )

    async def delete(self, path: str, **query: Any) -> JSONResponse:
        path = f"api/v1/{path}"
        return await JSONResponse.make(
            await self.__frontend.delete(
                path, params=API.processed_query(query), headers=self.__headers
            )
        )

    @contextlib.asynccontextmanager
    async def session(self, user: Union[User, AccessToken]) -> AsyncIterator[API]:
        async with self.frontend.session(user) as frontend:
            yield API(frontend, self.__anonymizer)

    async def with_session(
        self, user: User, operation: Callable[[API], Awaitable[T]]
    ) -> T:
        async with self.session(user) as api:
            return await operation(api)

    async def __check(
        self,
        verb: str,
        item_name: Optional[str],
        path: str,
        snapshot: bool,
        attributes: Collection[str],
        request: Awaitable[JSONResponse],
        keyed: Dict[str, Union[str, Sequence[str]]],
    ) -> Dict[str, Any]:
        _, _, resource_name = path.rpartition("/")
        response = raise_for_status(await request)
        (item,) = response.data[resource_name]
        if item_name is not None:
            for attribute in attributes:
                key = self.__anonymizer.find_key(
                    f"$.response.data.{resource_name}[*].{attribute}"
                )
                self.__anonymizer.define(**{key: {item_name: item[attribute]}})
        else:
            item_name = "<unnamed>"
        if snapshot:
            self.__anonymizer.assert_match(
                response, f"{verb} {resource_name}: {item_name}", **keyed
            )
        return item

    async def create(
        self,
        item_name: str,
        path: str,
        payload: Dict[str, Any],
        *,
        snapshot: bool = False,
        attributes: Collection[str] = ("id",),
        query: Dict[str, str] = {},
        **keyed: Union[str, Sequence[str]],
    ) -> Dict[str, Any]:
        return await self.__check(
            "created",
            item_name,
            path,
            snapshot,
            attributes,
            self.post(path, payload, **query),
            keyed,
        )

    async def fetch(
        self,
        item_name: Optional[str],
        path: str,
        *,
        snapshot: bool = False,
        attributes: Collection[str] = ("id",),
        query: Dict[str, str] = {},
        **keyed: Union[str, Sequence[str]],
    ) -> Dict[str, Any]:
        return await self.__check(
            "fetched",
            item_name,
            path,
            snapshot,
            attributes,
            self.get(path, **query),
            keyed,
        )


@pytest.fixture
def api(frontend: Frontend, anonymizer: Anonymizer) -> API:
    return API(frontend, anonymizer)
