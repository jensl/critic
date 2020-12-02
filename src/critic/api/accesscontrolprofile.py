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


class HTTPException(Protocol):
    """Representation of an exception for the "http" category

    The exception consists of the HTTP request method and a regular expression
    that must match the entire request path."""

    @property
    def id(self) -> int:
        ...

    @property
    def request_method(self) -> Optional[HTTPMethod]:
        ...

    @property
    def path_pattern(self) -> Optional[str]:
        ...


RepositoryAccessType = Literal["read", "modify"]
REPOSITORY_ACCESS_TYPES: FrozenSet[RepositoryAccessType] = frozenset(["read", "modify"])


class RepositoryException(Protocol):
    """Representation of an exception for the "repositories" category

    The exception consists of the access type ("read" or "modify") and the
    repository."""

    @property
    def id(self) -> int:
        ...

    @property
    def access_type(self) -> Optional[RepositoryAccessType]:
        ...

    @property
    def repository(self) -> Optional[api.repository.Repository]:
        ...


ExtensionAccessType = Literal["install", "execute"]
EXTENSION_ACCESS_TYPES: FrozenSet[ExtensionAccessType] = frozenset(
    ["install", "execute"]
)


class ExtensionException(Protocol):
    """Representation of an exception for the "extensions" category

    The exception consists of the access type ("install" or "execute")
    and the extension."""

    @property
    def id(self) -> int:
        ...

    @property
    def access_type(self) -> Optional[ExtensionAccessType]:
        ...

    @property
    def extension(self) -> Optional[api.extension.Extension]:
        ...


class AccessControlProfile(api.APIObject):
    """Representation of a an access control profile"""

    def __hash__(self) -> int:
        # Base class __hash__() fails for None.
        return hash(self.id)

    @property
    def id(self) -> Optional[int]:
        """The profile's unique id, or None

        None is returned for ephemeral profiles used when no actual profile
        is found to match the situation; e.g. the "allow everything" profile
        that is return by |fetch()| for the current session if no restricting
        profile is configured."""
        return self._impl.id

    @property
    def title(self) -> Optional[str]:
        """The profile's title, or None"""
        return self._impl.title

    @property
    async def access_token(self) -> Optional[api.accesstoken.AccessToken]:
        """The access token that owns this profile, or None"""
        return await self._impl.getAccessToken(self.critic)

    @property
    async def http(self) -> Category[HTTPException]:
        """Access control category "http"

        This category controls web frontend requests.

        Exceptions are of the type HTTPException."""
        return await self._impl.getHTTP(self.critic)

    @property
    async def repositories(self) -> Category[RepositoryException]:
        """Access control category "repositories"

        This category controls access to Git repositories, both via the web
        frontend and the Git hook.  Note that read-only Git access over SSH
        is not controlled by access control.

        Exceptions are of the type RepositoryException."""
        return await self._impl.getRepositories(self.critic)

    @property
    async def extensions(self) -> Category[ExtensionException]:
        """Access control category "extensions"

        This category controls access to any functionality provided by an
        extension.

        Exceptions are of the type ExtensionException."""
        return await self._impl.getExtensions(self.critic)


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
