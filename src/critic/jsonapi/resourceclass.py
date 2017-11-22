from __future__ import annotations

from abc import ABC, abstractmethod
from types import ModuleType
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from critic import api

from .exceptions import PathError


class NotSupported(Exception):
    pass


T = TypeVar("T")


class ResourceClass(Generic[T], ABC):
    name: str
    value_class: Union[Type[T], Tuple[Type[T]]]
    contexts: Tuple[Optional[str], ...] = (None,)
    exceptions: Tuple[Type[BaseException], ...]
    anonymous_create: bool = False
    anonymous_update: bool = False
    anonymous_delete: bool = False

    def __init_subclass__(
        cls,
        resource_name: str = None,
        value_class: Union[Type[T], Tuple[Type[T]]] = None,
        api_module: ModuleType = None,
        exceptions: Tuple[Type[BaseException], ...] = None,
    ) -> None:
        if api_module:
            cls.name = getattr(api_module, "resource_name")
            cls.value_class = api.get_value_class(api_module)
            cls.exceptions = (
                getattr(api_module, "Error") if exceptions is None else exceptions
            )
        else:
            assert resource_name
            cls.name = resource_name
            assert value_class
            cls.value_class = value_class
            cls.exceptions = exceptions or ()

        if None in cls.contexts:
            registerHandler("v1/" + cls.name, cls)
        for context in filter(None, cls.contexts):
            context, _, nested_name = context.partition(":")
            if not nested_name:
                nested_name = cls.name
            registerHandler(".../%s/%s" % (context, nested_name), cls)

    @staticmethod
    def resource_id(value: T) -> Any:
        return getattr(value, "id")

    @staticmethod
    @abstractmethod
    async def json(parameters: Parameters, value: T) -> JSONResult:
        ...

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> T:
        return (await cls.many(parameters, [argument]))[0]

    @classmethod
    async def many(
        cls, parameters: Parameters, arguments: Sequence[str]
    ) -> Sequence[T]:
        return [await cls.single(parameters, argument) for argument in arguments]

    @staticmethod
    async def multiple(parameters: Parameters) -> Union[T, Sequence[T]]:
        raise NotSupported()

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> Union[T, Sequence[T]]:
        raise NotSupported()

    @staticmethod
    async def update(
        parameters: Parameters, values: Values[T], data: JSONInput
    ) -> None:
        raise NotSupported()

    @staticmethod
    async def update_many(parameters: Parameters, data: Sequence[JSONInput]) -> None:
        raise NotSupported()

    @staticmethod
    async def delete(
        parameters: Parameters, values: Values[T]
    ) -> Optional[Union[T, Sequence[T]]]:
        raise NotSupported()

    @staticmethod
    async def setAsContext(parameters: Parameters, value: T) -> None:
        pass

    @staticmethod
    async def deduce(parameters: Parameters) -> Optional[T]:
        pass

    @staticmethod
    def find(value: object) -> Type[ResourceClass]:
        return HANDLERS[VALUE_CLASSES[type(value)]]

    @staticmethod
    def lookup(resource_path: Union[str, List[str]]) -> Type[ResourceClass]:
        if not isinstance(resource_path, list):
            resource_path = resource_path.split("/")
        for offset in range(len(resource_path) - 1):
            if offset:
                resource_id = "/".join(["..."] + resource_path[offset:])
            else:
                resource_id = "/".join(resource_path)
            try:
                return HANDLERS[resource_id]
            except KeyError:
                continue
        raise PathError("Invalid resource: %r" % "/".join(resource_path))

    @classmethod
    async def fromParameter(cls, parameters: Parameters, name: str) -> Optional[T]:
        value = parameters.getQueryParameter(name)
        if value is None:
            return None
        return await cls.fromParameterValue(parameters, value)

    @staticmethod
    async def fromParameterValue(parameters: Parameters, value: str) -> T:
        raise NotSupported()

    @staticmethod
    def sort_key(item: Dict[str, Any]) -> Any:
        return item["id"]


HANDLERS: Dict[str, Type[ResourceClass]] = {}
VALUE_CLASSES: Dict[type, str] = {}


def registerHandler(path: str, resource_class: Type[ResourceClass]) -> None:
    HANDLERS[path] = resource_class
    if not path.startswith("..."):
        if isinstance(resource_class.value_class, tuple):
            for value_class in resource_class.value_class:
                VALUE_CLASSES[value_class] = path
        else:
            VALUE_CLASSES[resource_class.value_class] = path


from .parameters import Parameters
from .values import Values
from .types import JSONInput, JSONResult
