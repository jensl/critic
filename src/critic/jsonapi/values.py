from __future__ import annotations

from typing import TypeVar, Union, Sequence, Iterable, Tuple, cast

T = TypeVar("T")


class Values(Tuple[T, ...]):
    @staticmethod
    def make(value_or_values: Union[T, Sequence[T]]) -> Values[T]:
        try:
            iter(cast(Iterable[T], value_or_values))
        except TypeError:
            return SingleValue[T](cast(T, value_or_values))
        else:
            return MultipleValues[T](cast(Sequence[T], value_or_values))


class SingleValue(Values[T]):
    def __new__(cls, value: T) -> SingleValue[T]:
        return super().__new__(cls, [value])

    def get(self) -> T:
        return self[0]


class MultipleValues(Values[T]):
    pass
