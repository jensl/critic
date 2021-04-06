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
from abc import abstractmethod
from dataclasses import dataclass

from typing import (
    Awaitable,
    Callable,
    Optional,
    Literal,
    Protocol,
    FrozenSet,
    Sequence,
    TypeVar,
)

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="access control profile"):
    """Base exception for all errors related to the AccessControlProfile
    class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid access control profile id is used"""

    pass


CategoryType = Literal["http", "repositories", "extensions"]

RuleValue = Literal["allow", "deny"]
RULE_VALUES: FrozenSet[RuleValue] = frozenset(["allow", "deny"])

ExceptionType = TypeVar("ExceptionType", covariant=True)


class Category(Protocol[ExceptionType]):
    """Representation of an access control category

    Each category is controlled by a rule ("allow" or "deny") and a list of
    exceptions (possibly empty). The effective policy is the rule, unless an
    exception applies, in which case it's the opposite of the rule."""

    @property
    def rule(self) -> RuleValue:
        ...

    @property
    def exceptions(self) -> Sequence[ExceptionType]:
        ...


HTTPMethod = Literal["GET", "HEAD", "OPTIONS", "POST", "PUT", "DELETE"]
HTTP_METHODS: FrozenSet[HTTPMethod] = frozenset(
    ["GET", "HEAD", "OPTIONS", "POST", "PUT", "DELETE"]
)


@dataclass(frozen=True)
class HTTPException:
    id: int
    request_method: Optional[HTTPMethod]
    path_pattern: Optional[str]


@dataclass(frozen=True)
class HTTPCategory:
    rule: RuleValue
    exceptions: Sequence[HTTPException]


RepositoryAccessType = Literal["read", "modify"]
REPOSITORY_ACCESS_TYPES: FrozenSet[RepositoryAccessType] = frozenset(["read", "modify"])


@dataclass(frozen=True)
class RepositoryException:
    id: int
    access_type: Optional[RepositoryAccessType]
    repository: Optional[api.repository.Repository]


@dataclass(frozen=True)
class RepositoryCategory:
    rule: RuleValue
    exceptions: Sequence[RepositoryException]


ExtensionAccessType = Literal["install", "execute"]
EXTENSION_ACCESS_TYPES: FrozenSet[ExtensionAccessType] = frozenset(
    ["install", "execute"]
)


@dataclass(frozen=True)
class ExtensionException:
    id: int
    access_type: Optional[ExtensionAccessType]
    extension: Optional[api.extension.Extension]


@dataclass(frozen=True)
class ExtensionCategory:
    rule: RuleValue
    exceptions: Sequence[ExtensionException]


class AccessControlProfile(api.APIObjectWithId):
    """Representation of a an access control profile"""

    def __hash__(self) -> int:
        # Base class __hash__() fails for None.
        return hash(self.id)

    @property
    @abstractmethod
    def id(self) -> int:
        """The profile's unique id, or negative

        None is returned for ephemeral profiles used when no actual profile
        is found to match the situation; e.g. the "allow everything" profile
        that is return by |fetch()| for the current session if no restricting
        profile is configured."""
        ...

    @property
    @abstractmethod
    def title(self) -> Optional[str]:
        """The profile's title, or None"""
        ...

    @property
    @abstractmethod
    async def access_token(self) -> Optional[api.accesstoken.AccessToken]:
        """The access token that owns this profile, or None"""
        ...

    @property
    @abstractmethod
    async def http(self) -> HTTPCategory:
        """Access control category "http"

        This category controls web frontend requests.

        Exceptions are of the type HTTPException."""
        ...

    @property
    @abstractmethod
    async def repositories(self) -> RepositoryCategory:
        """Access control category "repositories"

        This category controls access to Git repositories, both via the web
        frontend and the Git hook.  Note that read-only Git access over SSH
        is not controlled by access control.

        Exceptions are of the type RepositoryException."""
        ...

    @property
    @abstractmethod
    async def extensions(self) -> ExtensionCategory:
        """Access control category "extensions"

        This category controls access to any functionality provided by an
        extension.

        Exceptions are of the type ExtensionException."""
        ...


async def fetch(
    critic: api.critic.Critic, profile_id: Optional[int] = None, /
) -> AccessControlProfile:
    """Fetch an AccessControlProfile object with the given profile id

    If no profile id is given, then fetch the base access control profile for
    the current session (i.e. for the currently signed in user, or for the
    anonymous user.)"""
    return await fetchImpl.get()(critic, profile_id)


async def fetchAll(
    critic: api.critic.Critic, /, *, title: Optional[str] = None
) -> Sequence[AccessControlProfile]:
    """Fetch AccessControlProfile objects for all primary profiles in the system

    A profile is primary if it is not the additional restrictions imposed for
    accesses authenticated with an access token.

    If |title| is not None, fetch only profiles with a matching title."""
    return await fetchAllImpl.get()(critic, title)


resource_name = table_name = "accesscontrolprofiles"


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, Optional[int]], Awaitable[AccessControlProfile]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[str]], Awaitable[Sequence[AccessControlProfile]]
    ]
] = FunctionRef()
