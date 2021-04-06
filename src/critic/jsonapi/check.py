# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import logging
import re
from types import ModuleType
from typing import (
    Any,
    Collection,
    Dict,
    Optional,
    Union,
    Iterator,
    Tuple,
    Type,
    Generic,
    TypeVar,
    List,
    Iterable,
    Protocol,
    Sequence,
    Mapping,
    Container,
    cast,
    overload,
)

logger = logging.getLogger(__name__)

from critic import api

from .exceptions import InputError
from .parameters import Parameters
from .types import JSONInput, JSONInputItem
from .utils import maybe_await


def ishashable(value: Any) -> bool:
    try:
        hash(value)
    except TypeError:
        return False
    else:
        return True


class TypeCheckerContext(object):
    __repository: Optional[api.repository.Repository]
    __review: Optional[api.review.Review]

    def __init__(self, parameters: Parameters):
        self.critic = parameters.critic
        self.__repository = parameters.in_context(api.repository.Repository)
        self.__review = parameters.in_context(api.review.Review)
        self.__path = ["data"]

    @contextlib.contextmanager
    def push(self, element: Union[int, str]) -> Iterator[None]:
        if isinstance(element, int):
            self.__path.append("[%d]" % element)
        else:
            self.__path.append("." + str(element))
        yield
        self.__path.pop()

    def __str__(self) -> str:
        return "".join(self.__path)

    @property
    def review(self) -> Optional[api.review.Review]:
        return self.__review

    @review.setter
    def review(self, review: Optional[api.review.Review]) -> None:
        assert self.__review is None or self.__review == review
        self.__review = review

    @property
    def repository(self) -> Optional[api.repository.Repository]:
        return self.__repository

    @repository.setter
    def repository(self, repository: Optional[api.repository.Repository]) -> None:
        assert self.__repository is None or self.__repository == repository
        self.__repository = repository


class Error(Exception):
    pass


Intermediate = TypeVar("Intermediate")
Final = TypeVar("Final")


class TypeCheckerBase(Generic[Intermediate, Final]):
    expected_type: str = "something"
    convert_exception: Tuple[Type[BaseException], ...] = ()
    required_isinstance: type = object

    async def __call__(
        self, context: TypeCheckerContext, value: JSONInputItem
    ) -> Final:
        if not self.check_compatibility(context, value):
            raise InputError("%s: expected %s, got %r" % (context, self, value))
        try:
            intermediate = await self.check(context, value)
        except Error as error:
            raise InputError("%s: %s" % (context, str(error)))
        try:
            converted = await self.convert(context, intermediate)
        except self.convert_exception as error:
            raise InputError("%s: %s" % (context, error))
        await self.process(context, converted)
        return converted

    def check_compatibility(
        self, context: TypeCheckerContext, value: JSONInputItem
    ) -> bool:
        return isinstance(value, self.required_isinstance)

    async def check(
        self, context: TypeCheckerContext, value: JSONInputItem
    ) -> Intermediate:
        return cast(Intermediate, value)

    async def convert(self, context: TypeCheckerContext, value: Intermediate) -> Final:
        return cast(Final, value)

    async def process(self, context: TypeCheckerContext, value: Final) -> None:
        pass


Result = TypeVar("Result", covariant=True)


class TypeCheckerCallable(Protocol[Result]):
    expected_type: str
    convert_exception: Tuple[Type[BaseException], ...]

    # @property
    # def expected_type(self) -> str:
    #     ...

    # @property
    # def convert_exception(self) -> Tuple[Type[BaseException], ...]:
    #     ...

    async def __call__(self, context: TypeCheckerContext, value: JSONInputItem) -> T:
        ...

    def check_compatibility(
        self, context: TypeCheckerContext, value: JSONInputItem
    ) -> bool:
        ...


T = TypeVar("T")


class TypeChecker(TypeCheckerBase[T, T]):
    def __str__(self) -> str:
        return self.expected_type

    def check_compatibility(
        self, context: TypeCheckerContext, value: JSONInputItem
    ) -> bool:
        return isinstance(value, self.required_isinstance)

    async def convert(self, context: TypeCheckerContext, value: T) -> T:
        return value

    async def process(self, context: TypeCheckerContext, value: T) -> None:
        pass


TypeCheckerMapped = Union[type, Type[api.APIObject]]
TypeCheckerInputAtom = Union[
    None,
    Type[bool],
    Type[float],
    Type[str],
    TypeCheckerCallable,
    Type[TypeCheckerBase],
    Type[api.APIObject],
    Container[str],
]
TypeCheckerInputItem4 = TypeCheckerInputAtom
TypeCheckerInputItem3 = Union[
    TypeCheckerInputAtom,
    Iterable[TypeCheckerInputItem4],
    Mapping[str, TypeCheckerInputItem4],
]
TypeCheckerInputItem2 = Union[
    TypeCheckerInputAtom,
    Iterable[TypeCheckerInputItem3],
    Mapping[str, TypeCheckerInputItem3],
]
TypeCheckerInputItem1 = Union[
    TypeCheckerInputAtom,
    Iterable[TypeCheckerInputItem2],
    Mapping[str, TypeCheckerInputItem2],
]
TypeCheckerInputItem = Union[
    TypeCheckerInputAtom,
    Iterable[TypeCheckerInputItem1],
    Mapping[str, TypeCheckerInputItem1],
]
TypeCheckerInput = Mapping[str, TypeCheckerInputItem1]


def makeTypeChecker(
    value: Optional[TypeCheckerInputItem],
) -> TypeCheckerBase[Any, Any]:
    if value is None:
        return TypeChecker()
    if isinstance(value, type):
        if issubclass(value, api.APIObject):
            value = APIOBJECT_MAP.get(APIObjectKey(value), value)
        else:
            value = TYPE_MAP.get(value, value)
    if isinstance(value, TypeCheckerBase):
        return value
    if isinstance(value, type) and issubclass(value, TypeCheckerBase):
        return value()  # type: ignore
    if isinstance(value, list):
        (item_checker,) = cast(List[TypeCheckerInputItem], value)
        return ListChecker(item_checker)
    if isinstance(value, (set, frozenset)):
        value_set = cast(Collection[object], value)
        if all(isinstance(item, str) for item in value_set):
            return EnumerationChecker(*cast(Collection[str], value_set))
        return VariantChecker[object](
            makeTypeChecker(cast(TypeCheckerInputItem, item)) for item in value_set
        )
    if isinstance(value, dict):
        return ObjectChecker(cast(TypeCheckerInput, value))
    if isinstance(value, type) and issubclass(value, api.APIObject):
        return APIObjectById(value)
    raise Exception("invalid checked type: %r" % value)


class ListChecker(TypeCheckerBase[List[JSONInputItem], List[T]]):
    required_isinstance = list
    checker: TypeCheckerCallable[T]

    def __init__(self, checker: TypeCheckerInputItem):
        self.checker = makeTypeChecker(checker)
        self.expected_type = "list of %s" % self.checker.expected_type

    async def convert(
        self, context: TypeCheckerContext, value: List[JSONInputItem]
    ) -> List[T]:
        result: List[T] = []
        for index, element in enumerate(value):
            with context.push(index):
                result.append(await self.checker(context, element))
        return result


class VariantChecker(TypeCheckerBase[JSONInputItem, T]):
    types: Optional[Iterable[TypeCheckerCallable[T]]]
    matched: Optional[TypeCheckerCallable[T]]

    def __init_subclass__(
        cls, types: Optional[Iterable[TypeCheckerCallable[T]]] = None
    ):
        cls.types = types

    def __init__(self, types: Optional[Iterable[TypeCheckerCallable[T]]] = None):
        if types is None:
            types = self.types
            assert types
        self.checkers = list(types)
        self.matched = None
        expected_types = sorted(checker.expected_type for checker in self.checkers)
        self.expected_type = "%s or %s" % (
            ", ".join(map(str, expected_types[:-1])),
            expected_types[-1],
        )

    def check_compatibility(
        self, context: TypeCheckerContext, value: JSONInputItem
    ) -> bool:
        assert self.types
        for checker in self.types:
            logger.debug(f"{checker=} {value=}")
            if checker.check_compatibility(context, value):
                self.matched = checker
                self.convert_exception = checker.convert_exception
                return True
        return False

    async def convert(self, context: TypeCheckerContext, value: JSONInputItem) -> T:
        assert self.matched
        try:
            return await self.matched(context, value)
        finally:
            self.matched = None


class ObjectChecker(TypeCheckerBase[Mapping[str, JSONInputItem], Mapping[str, Any]]):
    required_isinstance = dict
    expected_type = "object"

    def __init__(self, attributes: TypeCheckerInput):
        self.attributes = {}
        self.prioritized = set()
        for attribute_name, attribute_type in attributes.items():
            required = False
            default = False
            if attribute_name.endswith("=null"):
                default = True
                attribute_name = attribute_name[:-5]
            elif attribute_name.endswith("?"):
                attribute_name = attribute_name[:-1]
            else:
                required = True
            if attribute_name.endswith("!"):
                attribute_name = attribute_name[:-1]
                self.prioritized.add(attribute_name)
            self.attributes[attribute_name] = (
                required,
                default,
                makeTypeChecker(attribute_type),
            )

    def __repr__(self) -> str:
        return repr(self.attributes)

    async def convert(
        self, context: TypeCheckerContext, value: Mapping[str, JSONInputItem]
    ) -> Mapping[str, Any]:
        result = {}

        async def convert_attributes(
            attributes: Iterable[Tuple[str, JSONInputItem]]
        ) -> None:
            for attribute_name, attribute_value in attributes:
                with context.push(attribute_name):
                    if attribute_name not in self.attributes:
                        raise InputError("%s: unexpected attribute" % context)
                    checker = self.attributes[attribute_name][2]
                    result[attribute_name] = await checker(context, attribute_value)

        await convert_attributes(
            (attribute_name, attribute_value)
            for attribute_name, attribute_value in value.items()
            if attribute_name in self.prioritized
        )
        await convert_attributes(
            (attribute_name, attribute_value)
            for attribute_name, attribute_value in value.items()
            if attribute_name not in self.prioritized
        )
        for attribute_name, (required, default, _) in self.attributes.items():
            if attribute_name not in result:
                if required:
                    with context.push(attribute_name):
                        raise InputError("%s: missing attribute" % context)
                elif default:
                    result[attribute_name] = None
        return result


class IntegerChecker(TypeChecker[int]):
    required_isinstance = int
    expected_type = "integer"


class RestrictedInteger(IntegerChecker):
    minvalue: Optional[int] = None
    maxvalue: Optional[int] = None

    def __init__(self, minvalue: Optional[int] = None, maxvalue: Optional[int] = None):
        if minvalue is not None:
            self.minvalue = minvalue
        if maxvalue is not None:
            self.maxvalue = maxvalue

    async def check(self, context: TypeCheckerContext, value: JSONInputItem) -> int:
        value = await super().check(context, value)
        if self.minvalue is not None and value < self.minvalue:
            raise Error(f"must be at least {self.minvalue}")
        if self.maxvalue is not None and value > self.maxvalue:
            raise Error(f"can be at most {self.maxvalue}")
        return value


class NonNegativeInteger(RestrictedInteger):
    minvalue = 0


class PositiveInteger(RestrictedInteger):
    minvalue = 1


class StringChecker(TypeChecker[str]):
    required_isinstance = str
    expected_type = "string"


class RestrictedString(StringChecker):
    def __init__(
        self,
        minlength: Optional[int] = None,
        maxlength: Optional[int] = None,
        regexp: Optional[str] = None,
    ):
        self.minlength = minlength
        self.maxlength = maxlength
        self.regexp = re.compile(regexp) if regexp else None

    async def check(self, context: TypeCheckerContext, value: JSONInputItem) -> str:
        value = await super().check(context, value)
        if self.minlength is not None and len(value) < self.minlength:
            raise Error("must be at least %d characters long" % self.minlength)
        if self.maxlength is not None and len(value) < self.maxlength:
            raise Error("can be at most %d characters long" % self.maxlength)
        if self.regexp is not None and not self.regexp.match(value):
            raise Error("must match '%s'" % self.regexp.pattern)
        return value


class RegularExpression(StringChecker):
    async def check(self, context: TypeCheckerContext, value: JSONInputItem) -> str:
        value = await super().check(context, value)
        try:
            re.compile(value)
        except re.error:
            raise Error("must be a valid Python regular expression")
        return value


class EnumerationChecker(StringChecker):
    def __init__(self, *values: str):
        self.values = frozenset(values)

    async def check(self, context: TypeCheckerContext, value: JSONInputItem) -> str:
        value = await super().check(context, value)
        if value not in self.values:
            values = sorted(self.values)
            raise Error(
                "must be one of %s and %s" % (", ".join(values[:-1]), values[-1])
            )
        return value


class BooleanChecker(TypeChecker[bool]):
    required_isinstance = bool
    expected_type = "boolean"


APIObjectClass = TypeVar("APIObjectClass", bound=api.APIObject)


class APIObject(TypeCheckerBase[Intermediate, APIObjectClass]):
    api_module: Optional[ModuleType]

    def __init_subclass__(cls, api_module: Optional[ModuleType] = None):
        super().__init_subclass__()
        cls.api_module = api_module

    def __init__(self, api_class: Optional[Type[APIObjectClass]] = None):
        if api_class is not None:
            self.api_module = api_class.getModule()
        assert self.api_module
        self.convert_exception = getattr(self.api_module, "Error")

    async def process(self, context: TypeCheckerContext, value: APIObjectClass) -> None:
        async def maybe_get(name: str) -> Any:
            return await maybe_await(getattr(value, name, None))

        if not context.review:
            context.review = await maybe_get("review")
        if not context.repository:
            context.repository = await maybe_get("repository")


class APIObjectById(APIObject[int, APIObjectClass]):
    intermediate_checker = PositiveInteger()

    def __init_subclass__(cls, api_module: ModuleType):
        super().__init_subclass__(api_module=api_module)

    def __init__(self, api_class: Optional[Type[APIObjectClass]] = None):
        super().__init__(api_class)
        if api_class is not None:
            self.api_module = api_class.getModule()
        self.convert_exception = getattr(self.api_module, "InvalidId")

    def check_compatibility(
        self, context: TypeCheckerContext, value: JSONInputItem
    ) -> bool:
        return self.intermediate_checker.check_compatibility(context, value)

    async def check(self, context: TypeCheckerContext, value: JSONInputItem) -> int:
        return await self.intermediate_checker.check(context, value)

    async def convert(self, context: TypeCheckerContext, value: int) -> APIObjectClass:
        return await getattr(self.api_module, "fetch")(context.critic, value)


class APIObjectByKey(APIObject[str, APIObjectClass]):
    intermediate_checker = StringChecker()

    key: str

    def __init_subclass__(cls, key: str, api_module: ModuleType):
        super().__init_subclass__(api_module=api_module)
        cls.key = key

    def __init__(self) -> None:
        super().__init__()
        self.convert_exception = getattr(self.api_module, "Error")

    def check_compatibility(
        self, context: TypeCheckerContext, value: JSONInputItem
    ) -> bool:
        return self.intermediate_checker.check_compatibility(context, value)

    async def check(self, context: TypeCheckerContext, value: JSONInputItem) -> str:
        return await self.intermediate_checker.check(context, value)

    async def convert(self, context: TypeCheckerContext, value: str) -> APIObjectClass:
        return await getattr(self.api_module, "fetch")(
            context.critic, **{self.key: value}
        )


class UserId(APIObjectById[api.user.User], api_module=api.user):
    pass


class UserName(APIObjectByKey[api.user.User], api_module=api.user, key="name"):
    pass


class User(
    VariantChecker[api.user.User],
    types={
        # TODO[typing]: These casts ought to be unnecessary.
        cast(TypeCheckerCallable[api.user.User], UserId()),
        cast(TypeCheckerCallable[api.user.User], UserName()),
    },
):
    pass


class RepositoryId(APIObjectById[api.repository.Repository], api_module=api.repository):
    pass


class RepositoryName(
    APIObjectByKey[api.repository.Repository], api_module=api.repository, key="name"
):
    pass


class Repository(
    VariantChecker[api.repository.Repository],
    types={
        # TODO[typing]: These casts ought to be unnecessary.
        cast(TypeCheckerCallable[api.repository.Repository], RepositoryId()),
        cast(TypeCheckerCallable[api.repository.Repository], RepositoryName()),
    },
):
    async def process(
        self, context: TypeCheckerContext, value: api.repository.Repository
    ) -> None:
        context.repository = value


class BranchId(APIObjectById[api.branch.Branch], api_module=api.repository):
    pass


class BranchName(
    APIObjectByKey[api.branch.Branch], api_module=api.repository, key="name"
):
    async def convert(
        self, context: TypeCheckerContext, value: str
    ) -> api.branch.Branch:
        if context.repository is None:
            raise Error("no repository set in context")
        return await api.branch.fetch(
            context.critic, repository=context.repository, name=value
        )


class Branch(
    VariantChecker[api.branch.Branch],
    types={
        # TODO[typing]: These casts ought to be unnecessary.
        cast(TypeCheckerCallable[api.branch.Branch], BranchId()),
        cast(TypeCheckerCallable[api.branch.Branch], BranchName()),
    },
):
    pass


class Review(APIObjectById[api.review.Review], api_module=api.review):
    async def process(
        self, context: TypeCheckerContext, value: api.review.Review
    ) -> None:
        context.review = value


class CommitId(APIObjectById[api.commit.Commit], api_module=api.commit):
    async def convert(
        self, context: TypeCheckerContext, value: int
    ) -> api.commit.Commit:
        if context.repository is None:
            raise Error("no repository set in context")
        return await api.commit.fetch(context.repository, value)


class CommitReference(
    APIObjectByKey[api.commit.Commit], api_module=api.commit, key="ref"
):
    convert_exception = (api.repository.InvalidRef,)

    async def convert(
        self, context: TypeCheckerContext, value: str
    ) -> api.commit.Commit:
        if context.repository is None:
            raise Error("no repository set in context")
        return await api.commit.fetch(context.repository, ref=value)


class Commit(
    VariantChecker[api.commit.Commit],
    types={
        # TODO[typing]: These casts ought to be unnecessary.
        cast(TypeCheckerCallable[api.commit.Commit], CommitId()),
        cast(TypeCheckerCallable[api.commit.Commit], CommitReference()),
    },
):
    pass


class FileId(APIObjectById[api.file.File], api_module=api.file):
    pass


class FilePath(APIObjectByKey[api.file.File], api_module=api.file, key="path"):
    convert_exception = (api.file.InvalidPath,)

    async def convert(self, context: TypeCheckerContext, value: str) -> api.file.File:
        return await api.file.fetch(context.critic, path=value, create_if_missing=True)


class File(
    VariantChecker[api.file.File],
    types={
        # TODO[typing]: These casts ought to be unnecessary.
        cast(TypeCheckerCallable[api.file.File], FileId()),
        cast(TypeCheckerCallable[api.file.File], FilePath()),
    },
):
    pass


class Changeset(APIObjectById[api.changeset.Changeset], api_module=api.changeset):
    pass


class ExtensionId(APIObjectById[api.extension.Extension], api_module=api.extension):
    pass


class ExtensionKey(
    APIObjectByKey[api.extension.Extension], api_module=api.extension, key="key"
):
    pass


class Extension(
    VariantChecker[api.extension.Extension],
    types={
        # TODO[typing]: These casts ought to be unnecessary.
        cast(TypeCheckerCallable[api.extension.Extension], ExtensionId()),
        cast(TypeCheckerCallable[api.extension.Extension], ExtensionKey()),
    },
):
    pass


class ReviewScopeId(
    APIObjectById[api.reviewscope.ReviewScope], api_module=api.reviewscope
):
    pass


class ReviewScopeName(
    APIObjectByKey[api.reviewscope.ReviewScope], api_module=api.reviewscope, key="name"
):
    pass


class ReviewScope(
    VariantChecker[api.reviewscope.ReviewScope],
    types={
        # TODO[typing]: These casts ought to be unnecessary.
        cast(TypeCheckerCallable[api.reviewscope.ReviewScope], ReviewScopeId()),
        cast(TypeCheckerCallable[api.reviewscope.ReviewScope], ReviewScopeName()),
    },
):
    pass


class Null(TypeChecker[Optional[T]]):
    expected_type = "null"

    def check_compatibility(
        self, context: TypeCheckerContext, value: JSONInputItem
    ) -> bool:
        return value is None


APIObjectType = TypeVar("APIObjectType", bound=api.APIObject)


class APIObjectKey:
    def __init__(self, cls: Any):
        self.__resource_name = cls.getResourceName()

    def __hash__(self) -> int:
        return hash(self.__resource_name)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, APIObjectKey)
            and self.__resource_name == other.__resource_name
        )


TYPE_MAP: Mapping[Any, Any] = {
    int: IntegerChecker(),
    str: StringChecker(),
    bool: BooleanChecker(),
}

APIOBJECT_MAP: Mapping[APIObjectKey, Any] = {
    APIObjectKey(api.user.User): User(),
    APIObjectKey(api.repository.Repository): Repository(),
    APIObjectKey(api.review.Review): Review(),
    APIObjectKey(api.commit.Commit): Commit(),
    APIObjectKey(api.file.File): File(),
    APIObjectKey(api.changeset.Changeset): Changeset(),
    APIObjectKey(api.extension.Extension): Extension(),
    APIObjectKey(api.reviewscope.ReviewScope): ReviewScope(),
    APIObjectKey(api.branch.Branch): Branch(),
}

Converted = Mapping[str, Any]


@overload
async def convert(
    parameters: Parameters,
    structure: TypeCheckerInput,
    value: JSONInput,
) -> Converted:
    ...


@overload
async def convert(
    parameters: Parameters,
    structure: TypeCheckerInput,
    value: JSONInput,
    resource_type: str,
) -> Tuple[Optional[Converted], Optional[Sequence[Converted]]]:
    ...


async def convert(
    parameters: Parameters,
    structure: TypeCheckerInput,
    value: JSONInput,
    resource_type: Optional[str] = None,
) -> Union[Converted, Tuple[Optional[Converted], Optional[Sequence[Converted]]]]:
    context = TypeCheckerContext(parameters)
    single_checker = makeTypeChecker(structure)
    if resource_type is not None:
        one = many = None
        if resource_type in value:
            many_checker = makeTypeChecker({resource_type: [single_checker]})
            many = (await many_checker(context, value))[resource_type]
        else:
            one = await single_checker(context, value)
        return one, many
    else:
        return await single_checker(context, value)


# def ensure(
#     data: JSONInput, path: Union[str, Sequence[str]], ensured_value: Any
# ) -> None:
#     if isinstance(path, str):
#         key = path
#     else:
#         for key in path[:-1]:
#             data = cast(Mapping[str, JSONInput], data)[key]
#         key = path[-1]

#     if key not in data:
#         data[key] = ensured_value
#     elif data[key] != ensured_value:
#         path_string = "data"
#         for key in path:
#             if isinstance(key, str):
#                 path_string += "." + key
#             else:
#                 path_string += "[%d]" % key
#         raise InputError("%s: must be %r or omitted" % (path_string, ensured_value))


@dataclass
class _Optional:
    spec: TypeCheckerInputItem1


def optional(spec: TypeCheckerInputItem1) -> _Optional:
    return _Optional(spec)


def anything() -> TypeCheckerInputAtom:
    return TypeChecker[Any]()


def input_spec(**items: Union[TypeCheckerInputItem1, _Optional]) -> TypeCheckerInput:
    result: Dict[str, TypeCheckerInputItem1] = {}
    for name, spec in items.items():
        if isinstance(spec, _Optional):
            name += "?"
            spec = spec.spec
        result[name] = spec
    return result
