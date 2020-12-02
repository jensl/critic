import asyncio
import functools
import logging
import os
import pickle
import struct
import sys
from typing import (
    AsyncIterator,
    Optional,
    Protocol,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)

from critic import api
from critic.background.extensionhost import (
    CallResponseItem,
    CallError,
    CommandPackage,
    ResponseErrorPackage,
    ResponseFinalPackage,
    ResponseItemPackage,
    ResponsePackage,
)


HEADER_FMT = "!I"


async def stdio(
    limit: int = 65536,
) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    loop = asyncio.get_running_loop()

    reader = asyncio.StreamReader(limit=limit, loop=loop)
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader, loop=loop), sys.stdin
    )

    writer_transport, writer_protocol = await loop.connect_write_pipe(
        lambda: asyncio.streams.FlowControlMixin(),
        os.fdopen(sys.stdout.fileno(), "wb"),
    )
    writer = asyncio.streams.StreamWriter(writer_transport, writer_protocol, None, loop)

    return reader, writer


class WriteResponse(Protocol):
    async def __call__(self, response: CallResponseItem, /) -> None:
        ...


async def write_message(
    writer: asyncio.StreamWriter, package: Union[CallError, ResponsePackage]
) -> None:
    package_data = pickle.dumps(package)
    writer.write(struct.pack(HEADER_FMT, len(package_data)))
    writer.write(package_data)
    await writer.drain()


class Runner:
    __token: Optional[str]

    def __init__(
        self,
        critic: api.critic.Critic,
        stdin: asyncio.StreamReader,
        stdout: asyncio.StreamWriter,
    ):
        self.__critic = critic
        self.stdin = stdin
        self.stdout = stdout

        self.__token = None

    @property
    def critic(self) -> api.critic.Critic:
        return self.__critic

    async def commands(self) -> AsyncIterator[Tuple[object, WriteResponse]]:
        async def write_response(token: str, response_item: CallResponseItem) -> None:
            await write_message(self.stdout, ResponseItemPackage(token, response_item))

        while True:
            try:
                header = await self.stdin.readexactly(struct.calcsize(HEADER_FMT))
            except asyncio.IncompleteReadError as error:
                assert not error.partial
                break

            package_len: int = struct.unpack(HEADER_FMT, header)[0]
            package = pickle.loads(await self.stdin.readexactly(package_len))

            assert isinstance(package, CommandPackage)

            logger.debug("incoming command package: %r", package)

            user: Optional[api.user.User]
            if isinstance(package.user_id, int):
                user = await api.user.fetch(self.critic, package.user_id)
            elif package.user_id == "anonymous":
                user = api.user.anonymous(self.critic)
            else:
                user = None

            accesstoken = (
                await api.accesstoken.fetch(self.critic, package.accesstoken_id)
                if package.accesstoken_id is not None
                else None
            )

            self.__token = package.token
            command = (
                package.command,
                functools.partial(write_response, package.token),
            )
            if user or accesstoken:
                with self.critic.user_session():
                    if user and not user.is_anonymous:
                        await self.critic.setActualUser(user)
                    if accesstoken:
                        await self.critic.setAccessToken(accesstoken)
                    yield command
            else:
                yield command
            await write_message(self.stdout, ResponseFinalPackage(package.token))
            self.__token = None

    async def handle_exception(self, details: str, traceback: str) -> bool:
        if self.__token is None:
            return False
        await write_message(
            self.stdout,
            ResponseErrorPackage(
                self.__token,
                CallError(
                    "Extension crashed while handling command", details, traceback
                ),
            ),
        )
        return True
