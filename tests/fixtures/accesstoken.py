from contextlib import asynccontextmanager
import pytest
from typing import (
    AsyncContextManager,
    AsyncIterator,
    Protocol,
)

from .api import API
from .instance import User
from ..utilities import AccessToken, Anonymizer


class CreateAccessToken(Protocol):
    def __call__(self, api: API, title: str) -> AsyncContextManager[AccessToken]:
        ...


@pytest.fixture
def create_access_token(api: API, anonymizer: Anonymizer) -> CreateAccessToken:
    @asynccontextmanager
    async def create(user: User, title: str) -> AsyncIterator[AccessToken]:
        payload = {"title": title}
        async with api.session(user) as session:
            token = AccessToken(
                await session.create(f"access token: {title}", "accesstokens", payload)
            )
        anonymizer.replace_string(token.value, f"AccessToken({title=})")
        try:
            yield token
        finally:
            async with api.session(user) as session:
                await session.delete(f"accesstokens/{token.id}")

    return create
