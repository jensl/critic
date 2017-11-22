from __future__ import annotations

from typing import Callable, Any, Union, Awaitable, TypeVar, Type, Set, List, Protocol

from .exceptions import ResourceSkipped
from .parameters import Parameters
from .resourceclass import ResourceClass
from .utils import maybe_await
from .values import Values
from .types import JSONResult

# JSONFunction = Callable[[Parameters, Any], Union[dict, Awaitable[dict]]]

T = TypeVar("T", contravariant=True)


class JSONFunction(Protocol[T]):
    def __call__(self, parameters: Parameters, value: T) -> JSONResult:
        ...


async def reduceValue(
    parameters: Parameters, json_fn: JSONFunction[T], value: T
) -> JSONResult:
    return await json_fn(parameters, value)


async def reduceValues(
    parameters: Parameters,
    json_fn: JSONFunction[T],
    values: Values[T],
    included_values: Set[Any],
) -> List[JSONResult]:
    if not values:
        return []

    json_objects = []

    for value in values:
        try:
            json_object = await json_fn(parameters, value)
        except ResourceSkipped:
            continue
        json_objects.append(json_object)
        try:
            included_values.add(value)
        except TypeError:
            pass

    return json_objects
