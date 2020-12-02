from __future__ import annotations

import inspect
from typing import (
    Any,
    Awaitable,
    Callable,
    Collection,
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

from .exceptions import PathError, UsageError
from .types import Request
from .valuewrapper import basic_list, ValueWrapper


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


async def maybe_await(result: Union[T, Awaitable[T]]) -> T:
    if not inspect.isawaitable(result):
        return cast(T, result)
    result = await cast(Awaitable[T], result)
    assert not inspect.isawaitable(result), result
    return result


class ObjectWithId(Protocol):
    @property
    def id(self) -> Any:
        ...


Sortable = TypeVar("Sortable", bound=ObjectWithId)


async def sorted_by_id(
    items: Union[
        Iterable[Sortable],
        Awaitable[Iterable[Sortable]],
        Callable[[], Union[Iterable[Sortable], Awaitable[Iterable[Sortable]]]],
    ],
) -> ValueWrapper[Collection[Sortable]]:
    if callable(items):
        items = items()
    items = await maybe_await(items)
    assert isinstance(items, Iterable)
    return basic_list(
        cast(Collection[Sortable], sorted(items, key=lambda item: item.id))
    )


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

    return api_version
