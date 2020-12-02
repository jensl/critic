from __future__ import annotations

import datetime
from typing import (
    Any,
    Collection,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
    cast,
)


class Adaptable(Protocol):
    def __adapt__(self) -> SQLValue:
        ...


SQLAtom = Union[bool, int, float, str, bytes, datetime.datetime, Adaptable]
SQLValue = Optional[Union[SQLAtom, Sequence[SQLAtom]]]
SQLRow = Tuple[SQLValue, ...]

Parameter = Union[SQLValue, Adaptable]
Parameters = Mapping[str, Parameter]
ExecuteArguments = Optional[Union[List[SQLValue], Parameters]]


def parameters(**kwargs: SQLValue) -> Parameters:
    return kwargs


def adapt(value: Any) -> Any:
    if value is None:
        return None
    __adapt__ = getattr(value, "__adapt__", None)
    if __adapt__:
        return __adapt__()
    if isinstance(value, (tuple, list, set)):
        return [adapt(item) for item in cast(Collection[Any], value)]
    return value
