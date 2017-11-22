import abc
import asyncio
import dataclasses
import json
import logging
import pytest
import subprocess
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterator,
    Dict,
    Literal, Protocol,
    Sequence,
    Tuple,
)

from ...utilities import ExecuteResult, Anonymizer, execute, raise_for_status

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class User:
    id: int
    name: str
    fullname: str
    email: str
    status: str
    password: str


class ExecuteError(Exception):
    def __init__(
        self, command: str, arguments: Sequence[str], stdout: str, stderr: str
    ):
        self.command = command
        self.arguments = arguments
        self.stdout = stdout
        self.stderr = stderr


class Instance(abc.ABC):
    users_by_name: Dict[str, User] = {}
    users_by_id: Dict[int, User] = {}

    address: Tuple[str, int]

    async def initialize(self):
        users = json.loads(
            raise_for_status(
                await self.execute("criticctl", "listusers", "--format=json")
            ).stdout
        )
        for user_data in users:
            user = User(**user_data, password=user_data["name"])
            self.users_by_name[user.name] = self.users_by_id[user.id] = user

    async def get_or_create_user(
        self, name: str, fullname: str, *, admin: bool = False
    ) -> Tuple[User, bool]:
        if name not in self.users_by_name:
            logger.info("Adding user: %s", name)
            user = User(
                len(self.users_by_name) + 1,
                name,
                fullname,
                f"{name}@example.org",
                "current",
                name,
            )
            roles = []
            if admin:
                roles.append("--role=administrator")
            raise_for_status(
                await self.execute(
                    "criticctl",
                    "adduser",
                    f"--username={user.name}",
                    f"--fullname={user.fullname}",
                    f"--email={user.email}",
                    f"--password={user.name}",
                    *roles,
                )
            )
            self.users_by_name[name] = user
            self.users_by_id[user.id] = user
            return user, True
        return self.users_by_name[name], False

    @abc.abstractmethod
    async def execute(
        self,
        program: Literal["criticctl"],
        *args: str,
        log_stdout: bool = True,
        log_stderr: bool = True,
    ) -> ExecuteResult:
        ...

    @abc.abstractmethod
    def run(self) -> AsyncContextManager[None]:
        ...

    @abc.abstractmethod
    def get_extension_url(self, name: str) -> str:
        ...


@pytest.fixture(scope="session")
async def instance(
    event_loop: asyncio.AbstractEventLoop, request: Any, workdir: str,
) -> AsyncIterator[Instance]:
    from .quickstart import Quickstart
    from .docker import Docker

    config = request.config
    instance_type = config.getoption("--instance-type")
    if instance_type == "quickstart":
        instance = Quickstart(config, workdir)
    # elif instance_type == "docker":
    #     instance = Docker(config, workdir)
    else:
        raise Exception(f"Invalid instance type: {instance_type}")

    async with instance.run():
        await instance.initialize()
        yield instance
