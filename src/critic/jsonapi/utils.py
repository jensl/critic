from __future__ import annotations

import inspect
from typing import (
    Any,
    Awaitable,
    Callable,
    Iterable,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from critic import api
from critic.jsonapi.valuewrapper import ValueWrapper, basic_list
from .exceptions import PathError, UsageError
from .types import Request


def id_or_name(argument: str) -> Tuple[Optional[int], Optional[str]]:
    try:
        return int(argument), None
    except ValueError:
        return None, argument


def numeric_id(argument: str) -> int:
    try:
        value = int(argument)
        if value < 1:
            raise ValueError
        return value
    except ValueError:
        raise UsageError("Invalid numeric id: %r" % argument)


T = TypeVar("T")


async def maybe_await(value: Union[T, Awaitable[T]]) -> T:
    if inspect.isawaitable(value):
        return await cast(Awaitable[T], value)
    return value  # type: ignore


Sortable = TypeVar("Sortable", bound=api.APIObjectWithId)


async def sorted_by_id(
    items: Union[Iterable[Sortable], Awaitable[Iterable[Sortable]]],
) -> ValueWrapper[Sequence[Sortable]]:
    if inspect.isawaitable(items):
        items = await cast(Awaitable[Iterable[Sortable]], items)
    return basic_list(sorted(cast(Iterable[Sortable], items), key=lambda item: item.id))


def many(converter: Callable[[str], T]) -> Callable[[str], Sequence[T]]:
    def inner(value: str) -> Sequence[T]:
        return [converter(item) for item in value.split(",")]

    return inner


async def delay(fn: Callable[[], Awaitable[T]]) -> T:
    return await fn()


def getAPIVersion(req: Request) -> Literal["v1"]:
    path = req.path.strip("/").split("/")

    assert len(path) >= 1 and path[0] == "api"

    if len(path) < 2:
        raise PathError("Missing API version")

    api_version = path[1]

    if api_version != "v1":
        raise PathError("Unsupported API version: %r" % api_version)

    return "v1"
