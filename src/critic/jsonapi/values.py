from __future__ import annotations

from typing import TypeVar, Union, Sequence, Tuple, cast

T = TypeVar("T")


class Values(Tuple[T, ...]):
    is_single: bool = False
    is_multiple: bool = False

    @classmethod
    def make(cls, value_or_values: Union[T, Sequence[T]]) -> Values[T]:
        try:
            iter(value_or_values)  # type: ignore
        except TypeError:
            return SingleValue[T](cast(T, value_or_values))
        else:
            return MultipleValues[T](cast(Sequence[T], value_or_values))

    def get(self) -> T:
        raise Exception("not a single value")


class SingleValue(Values[T]):
    is_single: bool = True

    def __new__(cls, value: T) -> SingleValue[T]:
        return super().__new__(cls, [value])

    def get(self) -> T:
        return self[0]


class MultipleValues(Values[T]):
    is_multiple: bool = True
