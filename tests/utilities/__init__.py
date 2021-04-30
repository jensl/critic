import asyncio
import hashlib
import secrets
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
    overload,
)


def generate_name(base: str) -> str:
    return f"{base}---{secrets.token_hex(4)}"


class Snapshot(Protocol):
    def assert_match(self, value: Any, label: str = None) -> None:
        ...


T = TypeVar("T")


class SupportsRaiseForStatus(Protocol):
    def raise_for_status(self) -> Any:
        ...


RaiseForStatus = TypeVar("RaiseForStatus", bound=SupportsRaiseForStatus)


def raise_for_status(result: RaiseForStatus) -> RaiseForStatus:
    return result.raise_for_status()


class SetContaining:
    def __init__(self, value: Any):
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, list) and self.value in other


class Blob:
    def __init__(self, title: str, data: str = None):
        self.title = title
        self.data = data if data is not None else title + "\n"

    @property
    def sha1(self) -> str:
        data = self.data.encode()
        return hashlib.sha1(b"blob %d\0%s" % (len(data), data)).hexdigest()


from .execute import ExecuteError, ExecuteResult, execute
from .filter import Anonymizer, Anonymous, Masked, Variable, Frozen


def map_to_id(
    items: List[Dict[str, Any]],
    key: Union[str, Callable[[Dict[str, Any]], str]],
    id_key="id",
) -> Dict[str, Any]:
    if callable(key):
        return {key(item): item[id_key] for item in items}
    return {item[key]: item[id_key] for item in items}


async def git(command: str, *argv: str, cwd: str = None) -> ExecuteResult:
    return await execute(
        f"git {command}",
        "git",
        command,
        *argv,
        cwd=cwd,
        env={
            "GIT_AUTHOR_NAME": "Critic Testing",
            "GIT_AUTHOR_EMAIL": "critic@example.org",
            "GIT_COMMITTER_NAME": "Critic Testing",
            "GIT_COMMITTER_EMAIL": "critic@example.org",
        },
    )


async def lsremote(url: str, ref: str = "HEAD") -> str:
    for line in raise_for_status(await git("ls-remote", url, ref)).stdout.splitlines():
        sha1, _, line_ref = line.partition("\t")
        if line_ref == ref:
            return sha1
    raise Exception(f"ref {ref!r} not found in {url}")


class AccessToken:
    __value: Optional[str]

    def __init__(self, data: Dict[str, object]):
        assert isinstance(data["id"], int)
        self.__id = data["id"]
        if "token" in data:
            assert isinstance(data["token"], str)
            self.__value = data["token"]
        else:
            self.__value = None

    @property
    def id(self) -> int:
        return self.__id

    @property
    def value(self) -> str:
        assert self.__value is not None
        return self.__value
