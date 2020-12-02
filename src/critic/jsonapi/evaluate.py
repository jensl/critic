from __future__ import annotations

import itertools
import logging
from typing import Iterable, Type, Sequence, cast

logger = logging.getLogger(__name__)

from .resourceclass import ResourceClass, APIObject


async def evaluateSingle(
    parameters: Parameters,
    resource_class: Type[ResourceClass[APIObject]],
    argument: str,
) -> Values[APIObject]:
    with parameters.forResource(resource_class.name):
        value = await resource_class.single(parameters, argument)
        assert isinstance(value, resource_class.value_class)  # type: ignore

    await resource_class.setAsContext(parameters, value)
    return SingleValue(value)


async def evaluateMany(
    parameters: Parameters,
    resource_class: Type[ResourceClass[APIObject]],
    arguments: Sequence[str],
) -> Values[APIObject]:
    with parameters.forResource(resource_class.name):
        values = await resource_class.many(parameters, arguments)

    assert all(isinstance(value, resource_class.value_class) for value in values)  # type: ignore
    return MultipleValues(values)


async def evaluateMultiple(
    parameters: Parameters, resource_class: Type[ResourceClass[APIObject]]
) -> Values[APIObject]:
    with parameters.forResource(resource_class.name):
        value_or_values = await resource_class.multiple(parameters)

    try:
        iter(value_or_values)  # type: ignore
    except TypeError:
        assert isinstance(value_or_values, resource_class.value_class)  # type: ignore
        single_value = cast(APIObject, value_or_values)
        await resource_class.setAsContext(parameters, single_value)
        return SingleValue(single_value)

    values = cast(Iterable[APIObject], value_or_values)

    if not parameters.range_accessed:
        begin, end = parameters.getRange()
        if begin is not None or end is not None:
            values = itertools.islice(values, begin, end)

    try:
        return MultipleValues(values)
    except Exception:
        logger.error(repr(values))
        raise


from .resourceclass import ResourceClass
from .parameters import Parameters
from .values import Values, SingleValue, MultipleValues
