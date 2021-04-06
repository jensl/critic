import asyncio
import json
import logging
import os
import secrets
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

from .arguments import Arguments


async def docker(command: str, *args: str) -> str:
    process = await asyncio.create_subprocess_exec(
        "docker", command, *args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error("Failed!")
        if stderr:
            logger.error(stderr.decode())
        raise Exception(f"'docker {command}' command failed")
    return stdout.decode()


class Database:
    container_id: Optional[str]
    host: Optional[str]
    port = 5432

    def __init__(self, arguments: Arguments, state_dir: str, state_is_temporary: bool):
        self.state_dir = state_dir
        self.state_is_temporary = state_is_temporary
        self.name = arguments.database_name
        self.password = self.get_password(arguments)
        self.username = arguments.database_username

        self.container_id = None
        self.host = None

    def get_password(self, arguments: Arguments) -> str:
        if arguments.database_password is not None:
            return arguments.database_password

        password_filename = os.path.join(self.state_dir, ".databasepw")
        if os.path.isfile(password_filename):
            with open(password_filename) as password_file:
                return json.load(password_file)

        # Generate a password that doesn't start with a dash, since we use it as a
        # command line argument.
        password = "-"
        while password.startswith("-"):
            password = secrets.token_urlsafe()
        with open(password_filename, "w") as password_file:
            json.dump(password, password_file)
        return password

    @property
    def container_name(self) -> str:
        return "critic_quickstart_database"

    async def find_container(self) -> Optional[str]:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "ps",
            "--filter",
            f"name={self.container_name}",
            "--quiet",
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        return stdout.decode().strip() or None

    async def start(self) -> bool:
        if (container_id := await self.find_container()) :
            logger.error("Database container already running!")
            logger.info("Hint: Run `docker stop %s` to stop it.", container_id)
            return False

        env = os.environ.copy()
        env_args = []

        def add_env(name: str, value: str) -> None:
            env[name] = value
            env_args.extend(["--env", name])

        add_env("POSTGRES_DB", self.name)
        add_env("POSTGRES_USER", self.username)
        if self.password:
            add_env("POSTGRES_PASSWORD", self.password)
        else:
            add_env("POSTGRES_HOST_AUTH_METHOD", "trust")

        pgdata = os.path.join(self.state_dir, "pgdata")
        if not os.path.isdir(pgdata):
            os.makedirs(pgdata)

        user_arg = (
            [
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--volume",
                "/etc/passwd:/etc/passwd:ro",
            ]
            if os.getuid() != 0
            else []
        )

        process = await asyncio.create_subprocess_exec(
            "docker",
            "run",
            "--name",
            f"critic_quickstart_database",
            "--rm",
            "--detach",
            *user_arg,
            "--volume",
            f"{pgdata}:/var/lib/postgresql/data",
            *env_args,
            "postgres:alpine",
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error("Failed!")
            if stderr:
                logger.error(stderr)
            return False

        self.container_id = stdout.decode().strip()
        logger.debug("database_container_id: %s", self.container_id)

        process = await asyncio.create_subprocess_exec(
            "docker",
            "container",
            "inspect",
            self.container_id,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error("Failed!")
            if stderr:
                logger.error(stderr)
            return False

        data = json.loads(stdout)
        self.host = data[0]["NetworkSettings"]["IPAddress"]
        logger.debug("database_host: %s", self.host)

        return True

    async def stop(self):
        if self.container_id is None:
            return

        time_arg = ["--time", "0"] if self.state_is_temporary else []

        process = await asyncio.create_subprocess_exec(
            "docker",
            "stop",
            *time_arg,
            self.container_id,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error("Failed!")
            if stderr:
                logger.error(stderr)
