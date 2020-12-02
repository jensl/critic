import aiohttp
import json
from typing import Any, Optional

from .arguments import get as get_arguments


class BadRequest(Exception):
    pass


class NotFound(Exception):
    pass


async def raise_for_status(response: aiohttp.ClientResponse) -> None:
    if response.status < 400:
        return
    if response.status < 500 and response.content_type == "application/json":
        json = await response.json()
        error = json["error"]
        if response.status == 400:
            raise BadRequest(f"{error['title']}: {error['message']}")
        if response.status == 404:
            raise NotFound(f"{error['title']}: {error['message']}")
    response.raise_for_status()


class Backend:
    user_id: Optional[int]

    def __init__(self, session: aiohttp.ClientSession):
        self.prefix = get_arguments().backend.rstrip("/")
        self.session = session
        self.user_id = None

    async def get(self, path: str, **params: str) -> Any:
        async with self.session.get(
            f"{self.prefix}/api/v1/{path}", params=params
        ) as response:
            await raise_for_status(response)
            return await response.json()

    async def post(self, path: str, payload: object, **params: str) -> Any:
        async with self.session.post(
            f"{self.prefix}/api/v1/{path}", data=json.dumps(payload), params=params
        ) as response:
            await raise_for_status(response)
            return await response.json()
