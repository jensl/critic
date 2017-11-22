from tests.utilities import raise_for_status
import pytest
from contextlib import asynccontextmanager
from typing import AsyncContextManager, AsyncIterator, Mapping, Protocol

from .api import API
from .instance import User
from .websocket import WebSocket
from ..utilities import raise_for_status


class Settings(Protocol):
    def __call__(self, settings: Mapping[str, object]) -> AsyncContextManager[None]:
        ...


@pytest.fixture
def settings(api: API, websocket: WebSocket, admin: User) -> Settings:
    @asynccontextmanager
    async def with_settings(settings: Mapping[str, object]) -> AsyncIterator[None]:
        async def put(session: API, key: str, value: object) -> None:
            setting = raise_for_status(
                await session.put("systemsettings", {"value": value}, key=key)
            ).data["systemsettings"][0]
            await websocket.pop(
                f"systemsettings/{setting['id']}", action="modified", key=key
            )
            await websocket.pop(
                "systemevents", action="created", category="settings", key=key
            )

        async with api.session(admin) as as_admin:
            restore_values = {}
            for key, new_value in settings.items():
                current_value = raise_for_status(
                    await as_admin.get("systemsettings", key=key)
                ).data["systemsettings"][0]["value"]
                if current_value == new_value:
                    continue
                restore_values[key] = current_value
                await put(as_admin, key, new_value)
            try:
                yield None
            finally:
                for key, previous_value in restore_values.items():
                    await put(as_admin, key, previous_value)

    return with_settings
