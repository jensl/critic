from __future__ import annotations

import itertools
import logging
from typing import Type, Iterable, Sequence, cast

logger = logging.getLogger(__name__)


async def evaluateSingle(
    parameters: Parameters, resource_class: Type[ResourceClass], argument: str
) -> Values:
    single = resource_class.single

    with parameters.forResource(resource_class):
        value = await resource_class.single(parameters, argument)
        assert isinstance(value, resource_class.value_class)

    await resource_class.setAsContext(parameters, value)
    return SingleValue(value)


async def evaluateMany(
    parameters: Parameters,
    resource_class: Type[ResourceClass],
    arguments: Sequence[str],
) -> Values:
    with parameters.forResource(resource_class):
        values = await resource_class.many(parameters, arguments)

    assert all(isinstance(value, resource_class.value_class) for value in values)
    return MultipleValues(values)


async def evaluateMultiple(
    parameters: Parameters, resource_class: Type[ResourceClass]
) -> Values:
    values: Iterable

    with parameters.forResource(resource_class):
        value_or_values = await resource_class.multiple(parameters)

    if isinstance(value_or_values, resource_class.value_class):
        await resource_class.setAsContext(parameters, value_or_values)
        return SingleValue(value_or_values)

    values = cast(Iterable, value_or_values)

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
