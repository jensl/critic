from __future__ import annotations

import aiosmtpd.handlers
import aiosmtpd.smtp
import asyncio
import email.message
import email.policy
import functools
import logging
import pytest
import snapshottest
from socket import AF_INET
from typing import Any, AsyncIterator, List

logger = logging.getLogger(__name__)

from .api import API
from .instance import User
from ..utilities.filter import Anonymizer


class Message:
    def __init__(self, source: email.message.EmailMessage):
        self.message_id = source.get("Message-Id")
        self.subject = source["Subject"]
        self.recipients = [str(address) for address in source["To"].addresses]
        self.body = source.get_payload()

    def to_json(self) -> Any:
        result = {
            "subject": self.subject,
            "recipients": self.recipients,
            "body": self.body,
        }
        if self.message_id:
            result["message-id"] = self.message_id
        return result


class MessageFormatter(snapshottest.formatters.BaseFormatter):
    def can_format(self, value: object) -> bool:
        return isinstance(value, Message)

    def format(self, value: Message, indent: Any, formatter: Any) -> Any:
        return snapshottest.formatters.format_dict(
            self.normalize(value, formatter), indent, formatter
        )

    def normalize(self, value: Message, formatter: Any) -> Any:
        return value.to_json()


snapshottest.formatter.Formatter.register_formatter(MessageFormatter())


class SMTPD(aiosmtpd.handlers.Message):
    messages: List[Message]
    port: int

    def __init__(self):
        super().__init__(email.message.EmailMessage)
        self.messages = []
        self.port = -1

    async def handle_RCPT(self, server, session, envelope, address, options) -> str:
        envelope.rcpt_options.extend(options)
        if address == "rejected@example.org":
            return "550 Rejected"
        envelope.rcpt_tos.append(address)
        return "250 OK"

    def prepare_message(
        self, session: aiosmtpd.smtp.Session, envelope: aiosmtpd.smtp.Envelope
    ) -> email.message.EmailMessage:
        message = email.message_from_bytes(
            envelope.content, policy=email.policy.default
        )
        assert isinstance(message, email.message.EmailMessage)
        return message

    def handle_message(self, message: email.message.EmailMessage) -> None:
        self.messages.append(Message(message))

    async def __aenter__(self) -> SMTPD:
        self.server = await asyncio.get_running_loop().create_server(
            functools.partial(aiosmtpd.smtp.SMTP, self), host="", port=0
        )
        assert self.server.sockets is not None
        for socket in self.server.sockets:
            if socket.family == AF_INET:
                self.port = socket.getsockname()[1]
                break
        else:
            assert False
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        self.server.close()
        await self.server.wait_closed()


@pytest.fixture
async def smtpd(api: API, admin: User, anonymizer: Anonymizer) -> AsyncIterator[SMTPD]:
    async with SMTPD() as smtpd:
        try:
            yield smtpd
        except:
            raise
        else:
            anonymizer.assert_match(smtpd.messages, "received emails")
