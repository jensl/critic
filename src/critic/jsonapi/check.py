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
import logging
import re
from abc import ABC, abstractmethod
from types import ModuleType
from typing import (
    Any,
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
    Set,
    FrozenSet,
    Sequence,
    Mapping,
    Container,
    cast,
    overload,
)

from critic.api import reviewscope

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi

from .types import JSONInputItem


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

    def __init__(self, parameters: jsonapi.Parameters):
        self.critic = parameters.critic
        self.__repository = parameters.context.get("repositories")
        self.__review = parameters.context.get("reviews")
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
            raise jsonapi.InputError("%s: expected %s" % (context, self))
        try:
            intermediate = await self.check(context, value)
        except Error as error:
            raise jsonapi.InputError("%s: %s" % (context, str(error)))
        try:
            converted = await self.convert(context, intermediate)
        except self.convert_exception as error:
            raise jsonapi.InputError("%s: %s" % (context, error))
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
    @property
    def expected_type(self) -> str:
        ...

    @property
    def convert_exception(self) -> Tuple[Type[BaseException], ...]:
        ...

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


def makeTypeChecker(value: Optional[TypeCheckerInputItem]) -> TypeCheckerBase:
    if value is None:
        return TypeChecker()
    if isinstance(value, type):
        value = CHECKER_MAP.get(value, value)
    if isinstance(value, TypeCheckerBase):
        return value
    if isinstance(value, type) and issubclass(value, TypeCheckerBase):
        return value()
    if isinstance(value, list):
        assert len(value) == 1
        return ListChecker(value[0])
    if isinstance(value, (set, frozenset)):
        if all(isinstance(item, str) for item in value):
            return EnumerationChecker(*value)
        return VariantChecker(
            makeTypeChecker(cast(TypeCheckerInputItem, item)) for item in value
        )
    if isinstance(value, dict):
        return ObjectChecker(cast(TypeCheckerInput, value))
    if isinstance(value, type) and issubclass(value, api.APIObject):
        return APIObjectById(value)
    raise Exception("invalid checked type: %r" % value)


class ListChecker(TypeCheckerBase[list, List[T]]):
    required_isinstance = list
    checker: TypeCheckerCallable[T]

    def __init__(self, checker: TypeCheckerInputItem):
        self.checker = makeTypeChecker(checker)
        self.expected_type = "list of %s" % self.checker.expected_type

    async def convert(self, context: TypeCheckerContext, value: list) -> List[T]:
        result: List[T] = []
        for index, element in enumerate(value):
            with context.push(index):
                result.append(await self.checker(context, element))
        return result


class VariantChecker(TypeCheckerBase[JSONInputItem, T]):
    types: Optional[Iterable[TypeCheckerCallable[T]]]
    matched: Optional[TypeCheckerCallable[T]]

    def __init_subclass__(cls, types: Iterable[TypeCheckerCallable[T]] = None):
        cls.types = types

    def __init__(self, types: Iterable[TypeCheckerCallable[T]] = None):
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
                        raise jsonapi.InputError("%s: unexpected attribute" % context)
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
                        raise jsonapi.InputError("%s: missing attribute" % context)
                elif default:
                    result[attribute_name] = None
        return result


class IntegerChecker(TypeChecker[int]):
    required_isinstance = int
    expected_type = "integer"


class RestrictedInteger(IntegerChecker):
    minvalue: Optional[int] = None
    maxvalue: Optional[int] = None

    def __init__(self, minvalue: int = None, maxvalue: int = None):
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
        self, minlength: int = None, maxlength: int = None, regexp: str = None
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


class BooleanChecker(TypeChecker):
    required_isinstance = bool
    expected_type = "boolean"


APIObjectClass = TypeVar("APIObjectClass", bound=api.APIObject)


class APIObject(TypeCheckerBase[Intermediate, APIObjectClass]):
    api_module: Optional[ModuleType]

    def __init_subclass__(cls, api_module: ModuleType = None):
        super().__init_subclass__()
        cls.api_module = api_module

    def __init__(self, api_class: Type[APIObjectClass] = None):
        if api_class is not None:
            self.api_module = api_class.getModule()
        assert self.api_module
        self.convert_exception = getattr(self.api_module, "Error")

    async def process(
        self, context: TypeCheckerContext, api_object: APIObjectClass
    ) -> None:
        async def maybe_get(name: str) -> Any:
            return await context.critic.maybe_await(getattr(api_object, name, None))

        if not context.review:
            context.review = await maybe_get("review")
        if not context.repository:
            context.repository = await maybe_get("repository")


class APIObjectById(APIObject[int, APIObjectClass]):
    intermediate_checker = PositiveInteger()

    def __init_subclass__(cls, api_module: ModuleType):
        super().__init_subclass__(api_module=api_module)

    def __init__(self, api_class: Type[APIObjectClass] = None):
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
        self, context: TypeCheckerContext, repository: api.repository.Repository
    ) -> None:
        context.repository = repository


class Review(APIObjectById[api.review.Review], api_module=api.review):
    async def process(
        self, context: TypeCheckerContext, review: api.review.Review
    ) -> None:
        context.review = review


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


CHECKER_MAP: Mapping[type, TypeCheckerBase] = {
    int: IntegerChecker(),
    str: StringChecker(),
    bool: BooleanChecker(),
    api.user.User: User(),
    api.repository.Repository: Repository(),
    api.review.Review: Review(),
    api.commit.Commit: Commit(),
    api.file.File: File(),
    api.changeset.Changeset: Changeset(),
    api.extension.Extension: Extension(),
    api.reviewscope.ReviewScope: ReviewScope(),
}

Converted = Mapping[str, Any]


@overload
async def convert(
    parameters: jsonapi.Parameters,
    structure: TypeCheckerInput,
    value: jsonapi.JSONInput,
) -> Converted:
    ...


@overload
async def convert(
    parameters: jsonapi.Parameters,
    structure: TypeCheckerInput,
    value: jsonapi.JSONInput,
    resource_type: str,
) -> Tuple[Optional[Converted], Optional[Sequence[Converted]]]:
    ...


async def convert(
    parameters: jsonapi.Parameters,
    structure: TypeCheckerInput,
    value: jsonapi.JSONInput,
    resource_type: str = None,
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


def ensure(data: jsonapi.JSONInput, path: str, ensured_value: Any) -> None:
    if isinstance(path, (tuple, list)):
        for key in path[:-1]:
            data = data[key]
        key = path[-1]
    else:
        key = path

    if key not in data:
        data[key] = ensured_value
    elif data[key] != ensured_value:
        path_string = "data"
        for key in path:
            if isinstance(key, str):
                path_string += "." + key
            else:
                path_string += "[%d]" % key
        raise jsonapi.InputError(
            "%s: must be %r or omitted" % (path_string, ensured_value)
        )
