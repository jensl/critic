import logging
import pytest

from ..fixtures.api import API
from ..fixtures.extension import CreateExtension, Extension
from ..fixtures.websocket import WebSocket
from ..fixtures.instance import Instance, User
from ..fixtures.smtpd import SMTPD
from ..fixtures.settings import Settings
from ..utilities import Anonymizer, raise_for_status, generate_name

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_email_delivery(
    instance: Instance,
    api: API,
    websocket: WebSocket,
    admin: User,
    alice: User,
    bob: User,
    anonymizer: Anonymizer,
    create_extension: CreateExtension,
    test_extension: Extension,
    smtpd: SMTPD,
    settings: Settings,
) -> None:
    async with create_extension(
        "email-delivery", instance.get_extension_url("email-delivery")
    ):
        async with settings(
            {"smtp.address.host": "localhost", "smtp.address.port": smtpd.port}
        ):
            message_id = generate_name("message-id")
            raise_for_status(
                await test_extension.get(
                    "main",
                    "send-email",
                    params={
                        "to": ", ".join(
                            [
                                alice.name,
                                f"That Bob <{bob.name}>",
                                "Someone Else <else@example.org>",
                            ]
                        ),
                        "message_id": message_id,
                    },
                )
            )
            await websocket.pop("email/outgoing")
            await websocket.expect("email/sent", message_id=message_id)

            message_id = generate_name("message-id")
            raise_for_status(
                await test_extension.get(
                    "main",
                    "send-email",
                    params={"to": "rejected@example.org", "message_id": message_id},
                )
            )
            await websocket.pop("email/outgoing")
            await websocket.expect("email/sent", message_id=message_id)
