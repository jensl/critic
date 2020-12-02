from __future__ import annotations

from typing import Generic, TypeVar, Collection


WrappedType = TypeVar("WrappedType")


class ValueWrapper(Generic[WrappedType]):
    def __init__(self, value: WrappedType):
        self.value = value


class PlainWrapper(ValueWrapper[WrappedType]):
    pass


class ImmediateWrapper(ValueWrapper[WrappedType]):
    pass


class BasicListWrapper(ImmediateWrapper[WrappedType]):
    pass


def plain(value: WrappedType) -> PlainWrapper[WrappedType]:
    """Wrap a value to signal that it needs no further processing"""
    return PlainWrapper(value)


def immediate(value: WrappedType) -> ImmediateWrapper[WrappedType]:
    """Wrap a value to signal that it contains no coroutines/futures"""
    return ImmediateWrapper(value)


def basic_list(value: Collection[WrappedType]) -> ValueWrapper[Collection[WrappedType]]:
    """Wrap a value to signal that it is a list of basic values"""
    return BasicListWrapper(value)
