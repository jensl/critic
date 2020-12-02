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

from abc import ABCMeta, abstractmethod
from typing import (
    ClassVar,
    Collection,
    Mapping,
    NamedTuple,
    Optional,
    Protocol,
    Sequence,
)

from critic import api
from critic import auth
from critic import base


class Modifier(Protocol):
    async def setPassword(self, *, hashed_password: str) -> None:
        ...


class Field(NamedTuple):
    hidden: bool
    identifier: str
    label: str
    description: Optional[str] = None


class Database(metaclass=ABCMeta):
    name: ClassVar[str]

    def __init_subclass__(cls, *, dbname: str) -> None:
        cls.name = dbname

    @staticmethod
    def get():
        from . import databases

        settings = api.critic.settings().authentication
        if settings.databases.internal.enabled:
            authdb = databases.internaldb.Internal()
        elif settings.databases.ldap.enabled:
            authdb = databases.ldapdb.LDAP()
        else:
            raise base.InvalidConfiguration("No authentication database enabled")

        if settings.enable_access_tokens:
            authdb = databases.accesstokensdb.AccessTokens(authdb)

        return authdb

    @property
    def configuration(self):
        return getattr(api.critic.settings().authentication.databases, self.name)

    @abstractmethod
    def getFields(self) -> Sequence[Field]:
        """The fields in the sign-in form

        The return value should be a sequence of tuples, with elements as
        follows:

        The first element should be a boolean.  True means the value should
        be hidden, e.g. that it's a password or similar.

        The second element should be an (in this context unique) identifer,
        for internal use.

        The third element should be the field's label in the login form,
        e.g. "Username" or "Email (@example.com)".

        The fourth element is optional; if present it should be a longer
        description of the field to be used in a help popup or similar.
        Note: this value is taken as HTML source text, meaning it can contain
        tags, but also that '<' and '&' characters must be replaced with &lt;
        and &amp; entity references."""
        ...

    @abstractmethod
    async def authenticate(
        self, critic: api.critic.Critic, fields: Mapping[str, str]
    ) -> api.user.User:
        """Authenticate user based on values input

        The |fields| argument is a dictionary mapping identifiers (the second
        element in the tuples returned by getFields()) to the values the user
        entered.

        On success, an api.user.User object must be returned.  No other type
        of return value is acceptable.

        On failure/error, either AuthenticationError or AuthenticationFailed
        should be raised.  Any other exception raised will be treated similar
        to an AuthenticationError exception."""
        ...

    async def getAuthenticationLabels(self, user: api.user.User) -> Collection[str]:
        return ()

    def supportsHTTPAuthentication(self) -> bool:
        """Returns true if HTTP authentication is supported

        By default it is if the database declares two fields, where the first
        is not hidden (not a password) and the second is hidden.  The first
        field will receive the HTTP username and the second field the HTTP
        password."""
        fields = self.getFields()
        return len(fields) == 2 and not fields[0][0] and fields[1][0]

    async def performHTTPAuthentication(
        self,
        critic: api.critic.Critic,
        *,
        username: Optional[str],
        password: Optional[str],
        token: Optional[str]
    ) -> api.user.User:
        raise auth.AuthenticationFailed("HTTP authentication not supported")

    def supportsPasswordChange(self) -> bool:
        """Returns true if password changing is supported"""
        return False

    async def changePassword(
        self,
        critic: api.critic.Critic,
        user: api.user.User,
        modifier: Modifier,
        current_pw: str,
        new_pw: str,
    ) -> None:
        """Change the user's password

        Raises auth.WrongPassword if |current_pw| is incorrect."""
        pass
