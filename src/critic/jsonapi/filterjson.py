from __future__ import annotations

import asyncio
import functools
import logging
from typing import (
    Collection,
    Coroutine,
    Mapping,
    Protocol,
    Type,
    Any,
    Tuple,
    Sequence,
    Optional,
    Iterable,
    cast,
)

logger = logging.getLogger(__name__)

from critic.base.profiling import timed

from .linked import Linked
from .parameters import Parameters
from .resourceclass import ResourceClass, APIObject, VALUE_CLASSES
from .types import JSONResult
from .utils import maybe_await
from .valuewrapper import ValueWrapper, PlainWrapper, BasicListWrapper


class CheckField(Protocol):
    def __call__(self, *keys: str, value: Any) -> Tuple[bool, Optional[CheckField]]:
        ...


class FilterQuick(Protocol):
    def __call__(
        self,
        json_object: JSONResult,
        check_field: Optional[CheckField] = None,
        root_result: Optional[JSONResult] = None,
    ) -> Any:
        ...


class FilterAsync(Protocol):
    async def __call__(
        self,
        json_object: JSONResult,
        check_field: Optional[CheckField] = None,
        root_result: Optional[JSONResult] = None,
    ) -> Any:
        ...


async def filter_json(
    parameters: Parameters,
    linked: Linked,
    resource_class: Type[ResourceClass[APIObject]],
    json_objects: Sequence[JSONResult],
) -> Any:
    resource_type = resource_class.name

    api_object_cache = parameters.api_object_cache

    def filter_basic(json_object: JSONResult) -> Any:
        try:
            return api_object_cache[id(json_object)]
        except KeyError:
            pass
        resource_path = VALUE_CLASSES.get(type(json_object))
        if resource_path is None:
            return json_object
        resource_class = linked.add(resource_path, json_object)
        resource_id = resource_class.resource_id(json_object)
        api_object_cache[id(json_object)] = resource_id
        return resource_id

    def filter_quick(
        json_object: JSONResult,
        check_field: Optional[CheckField] = None,
        root_result: Optional[JSONResult] = None,
    ) -> Any:
        filter_next: FilterQuick

        if isinstance(json_object, PlainWrapper):
            value = cast(PlainWrapper[object], json_object).value

            if not check_field:
                return value

            def filter_next_plain(
                json_object: JSONResult,
                check_field: Optional[CheckField] = None,
                root_result: Optional[JSONResult] = None,
            ) -> Any:
                return json_object

            json_object = value
            filter_next = filter_next_plain
        else:
            filter_next = cast(FilterQuick, filter_quick)

        if isinstance(json_object, BasicListWrapper):
            value = cast(BasicListWrapper[Collection[object]], json_object).value
            return [filter_basic(item) for item in value]
        if isinstance(json_object, dict):
            if check_field is not None:
                result: JSONResult = {}
                if root_result is None:
                    root_result = result
                assert root_result is not None
                for key, value in cast(Mapping[str, object], json_object).items():
                    include, child_check = check_field(key, value=value)
                    if include:
                        result[key] = filter_next(value, child_check, root_result)
                    else:
                        root_result["is_partial"] = True
                return result
            return {
                key: filter_next(value)
                for key, value in cast(Mapping[str, object], json_object).items()
            }
        if isinstance(json_object, list):
            return [filter_next(value) for value in cast(Sequence[object], json_object)]
        if isinstance(json_object, (set, frozenset)):
            return sorted(
                filter_next(value) for value in cast(Collection[object], json_object)
            )

        return filter_basic(json_object)

    async def filter_async(
        json_object: JSONResult,
        check_field: Optional[CheckField] = None,
        root_result: Optional[JSONResult] = None,
    ) -> Any:
        filter_next: FilterAsync = cast(FilterAsync, filter_async)
        json_object = await maybe_await(json_object)
        if isinstance(json_object, ValueWrapper):
            value = cast(ValueWrapper[object], json_object).value
            return filter_quick(cast(JSONResult, value), check_field, root_result)
        if isinstance(json_object, dict):
            if check_field:
                result: JSONResult = {}
                if root_result is None:
                    root_result = result
                assert root_result is not None
                for key, value in cast(Mapping[str, object], json_object).items():
                    include, child_check = check_field(key, value=value)
                    if include:
                        result[key] = await filter_next(value, child_check, root_result)
                    else:
                        root_result["is_partial"] = True
                return cast(Any, result)
            return cast(
                Any,
                {
                    key: await filter_next(value)
                    for key, value in cast(Mapping[str, object], json_object).items()
                },
            )
        if isinstance(json_object, list):
            return cast(
                Any,
                [
                    await filter_next(value)
                    for value in cast(Sequence[object], json_object)
                ],
            )
        if isinstance(json_object, (set, frozenset)):
            return cast(
                Any,
                sorted(
                    [
                        await filter_next(value)
                        for value in cast(Collection[object], json_object)
                    ]
                ),
            )
        return filter_basic(json_object)

    included, excluded = parameters.getFieldsForType(resource_type)

    def check_field(*keys: str, value: Any) -> Tuple[bool, Optional[CheckField]]:
        key = ".".join(keys)
        include = exact_match = False

        if key not in excluded:
            if included:
                exact_match = key in included
                include = exact_match or key + "." in included
            else:
                include = True

        if not include:
            _close(value)

        child_check: Optional[CheckField]
        if include and not exact_match:
            child_check = functools.partial(check_field, key)  # type: ignore
        else:
            child_check = None

        return include, child_check

    root_check: Optional[CheckField]
    if included or excluded:
        root_check = check_field
    else:
        root_check = None

    with timed("filter_json: %s (%d objects)" % (resource_type, len(json_objects))):
        if not json_objects:
            return []

        if isinstance(json_objects[0], PlainWrapper):
            assert all(
                isinstance(json_object, PlainWrapper) for json_object in json_objects
            )
            return [
                filter_quick(cast(JSONResult, json_object.value), root_check)
                for json_object in json_objects
            ]

        return [
            await filter_async(json_object, root_check) for json_object in json_objects
        ]


def _close(value: object) -> None:
    def close_all(values: Iterable[object]) -> None:
        for value in values:
            _close(value)

    if asyncio.iscoroutine(value):
        cast(Coroutine[Any, Any, Any], value).close()
    elif isinstance(value, (set, tuple, list)):
        close_all(cast(Iterable[object], value))
    elif isinstance(value, dict):
        close_all(cast(Mapping[object, object], value).values())
