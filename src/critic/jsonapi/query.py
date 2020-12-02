from typing import (
    Callable,
    Collection,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from .exceptions import UsageError

T = TypeVar("T")


class Query:
    __query_parameters: Mapping[str, str]
    __resource_type: Tuple[Callable[[], Optional[str]]]

    def __init__(
        self,
        query_parameters: Mapping[str, str],
        resource_type: Callable[[], Optional[str]],
    ):
        self.__query_parameters = query_parameters
        self.__resource_type = (resource_type,)

    @overload
    def get(
        self, name: str, /, *, choices: Optional[Collection[str]] = None
    ) -> Optional[str]:
        ...

    @overload
    def get(
        self, name: str, default: str, /, *, choices: Optional[Collection[str]] = None
    ) -> str:
        ...

    @overload
    def get(
        self,
        name: str,
        /,
        *,
        converter: Callable[[str], T],
        exceptions: Tuple[Type[BaseException], ...] = (ValueError,),
    ) -> Optional[T]:
        ...

    @overload
    def get(
        self,
        name: str,
        default: str,
        /,
        *,
        converter: Callable[[str], T],
        exceptions: Tuple[Type[BaseException], ...] = (ValueError,),
    ) -> T:
        ...

    def get(
        self,
        name: str,
        default: Optional[str] = None,
        /,
        *,
        choices: Optional[Collection[str]] = None,
        converter: Optional[Callable[[str], T]] = None,
        exceptions: Tuple[Type[BaseException], ...] = (ValueError,),
    ) -> Optional[Union[str, T]]:
        value: Optional[str] = None
        resource_type = self.__resource_type[0]()
        if resource_type:
            value = self.__query_parameters.get("%s[%s]" % (name, resource_type))
        if value is None:
            value = self.__query_parameters.get(name)
        if value is None:
            value = default
        if value is None:
            return None
        if converter:
            try:
                return converter(value)
            except exceptions as error:
                raise UsageError.invalidParameter(name, value, message=str(error))
        if choices:
            if value not in choices:
                choices = sorted(choices)
                expected = ", ".join(choices[:-1]) + " and " + choices[-1]
                raise UsageError.invalidParameter(
                    name, value, expected=f"one of {expected}"
                )
        return value
