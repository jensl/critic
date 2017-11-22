import logging
import pytest

from ..fixtures.api import API
from ..fixtures.frontend import Frontend
from ..fixtures.extension import CreateExtension, Extension
from ..fixtures.websocket import WebSocket
from ..fixtures.instance import Instance, User
from ..fixtures.smtpd import SMTPD
from ..fixtures.settings import Settings
from ..fixtures.accesstoken import CreateAccessToken, create_access_token
from ..utilities import AccessToken, Anonymizer, raise_for_status, generate_name

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_endpoint(
    frontend: Frontend,
    api: API,
    alice: User,
    anonymizer: Anonymizer,
    test_extension: Extension,
    create_access_token: CreateAccessToken,
) -> None:
    anonymizer.assert_match(
        raise_for_status(await test_extension.get("main", "echo")), "simple GET"
    )

    anonymizer.assert_match(
        raise_for_status(
            await test_extension.get(
                "main", "echo", params={"foo": "FOO", "bar": "BAR"}
            )
        ),
        "GET with parameters",
    )

    anonymizer.assert_match(
        raise_for_status(await test_extension.post("main", "echo", "plain text")),
        "POST of plain text",
    )

    anonymizer.assert_match(
        raise_for_status(await test_extension.put("main", "echo", {"type": "JSON"})),
        "PUT of JSON",
    )

    anonymizer.assert_match(
        raise_for_status(
            await test_extension.put("main", "echo", b"null terminated\0")
        ),
        "PUT of binary data",
    )

    anonymizer.assert_match(
        raise_for_status(await test_extension.delete("main", "echo")), "DELETE"
    )

    async with test_extension.session(alice) as as_alice_extension:
        anonymizer.assert_match(
            raise_for_status(await as_alice_extension.get("main", "echo")),
            "alice with password",
        )

    async with create_access_token(alice, "test_endpoint") as token:
        async with test_extension.session(token) as as_alice_extension:
            anonymizer.assert_match(
                raise_for_status(await as_alice_extension.get("main", "echo")),
                "alice with access token",
            )
