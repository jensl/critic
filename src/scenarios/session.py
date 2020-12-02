from typing import AsyncIterator, Optional
import aiohttp
from contextlib import asynccontextmanager
import json
import logging

logger = logging.getLogger(__name__)

from .arguments import get as get_arguments
from .backend import Backend

DEFAULT_PASSWORD = "testing"


@asynccontextmanager
async def session(
    username: Optional[str] = None, password: Optional[str] = None
) -> AsyncIterator[Backend]:
    arguments = get_arguments()

    if username is None:
        username = arguments.admin_username
        if password is None:
            password = arguments.admin_password
    elif password is None:
        password = DEFAULT_PASSWORD

    async with aiohttp.ClientSession() as client_session:
        backend = Backend(client_session)
        response = await backend.post(
            "sessions",
            {"username": username, "password": password},
        )
        backend.user_id = response["user"]
        yield backend
