# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

import base64
import os
import re
import logging
import time
from typing import Any, Callable, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess


class AuthenticationError(Exception):
    """Raised by Database.authenticate() on error

    "Error" here means something the system administrator should be informed
    about, rather than the user.

    The user trying to sign in will not see this exception's message, but
    will instead be shown a generic error message saying that something went
    wrong."""

    pass


class AuthenticationFailed(Exception):
    """Raised by Database.authenticate() on failure

    "Failure" here means the identification and/or password provided by the
    user was incorrect.

    The user trying to sign in will be presented with this exception's
    message as the reason for the failure.  Note: this value is taken as HTML
    source text, meaning it can contain tags, but also that '<' and '&'
    characters must be replaced with &lt; and &amp; entity references."""

    def __init__(self, *args: Any, field_name: Optional[str] = None):
        super().__init__(*args)
        self.field_name = field_name


class InvalidUsername(AuthenticationFailed):
    """Raised by Database.authenticate() when an invalid username was used"""

    pass


class WrongPassword(AuthenticationFailed):
    """Raised by Database.authenticate() when an incorrect password was used"""

    pass


class InvalidToken(AuthenticationFailed):
    """Raised by Database.authenticate() when an invalid token was used"""

    pass


class CryptContext(Protocol):
    def hash(self, password: str) -> str:
        ...

    def verify_and_update(
        self, password: str, hashed: str
    ) -> Tuple[bool, Optional[str]]:
        ...


def createCryptContext() -> CryptContext:
    settings = api.critic.settings().authentication.databases.internal

    try:
        from passlib.context import CryptContext as PasslibCryptContext

        kwargs = {f"{settings.used_scheme}__min_rounds": settings.minimum_rounds}

        return PasslibCryptContext(
            schemes=settings.accepted_schemes,
            default=settings.used_scheme,
            deprecated=[
                scheme
                for scheme in settings.accepted_schemes
                if scheme != settings.used_scheme
            ],
            **kwargs,
        )
    except ImportError:
        if not settings.system.is_quickstart:
            raise

    # Support quick-starting without 'passlib' installed by falling back to
    # completely bogus unsalted SHA-256-based hashing.

    import hashlib

    class FallbackCryptContext:
        def hash(self, password: str) -> str:
            return hashlib.sha256(password.encode()).hexdigest()

        def verify_and_update(
            self, password: str, hashed: str
        ) -> Tuple[bool, Optional[str]]:
            return self.hash(password) == hashed, None

    return FallbackCryptContext()


async def checkPassword(
    critic: api.critic.Critic, username: str, password: str
) -> api.user.User:
    async with api.critic.Query[Tuple[int, str]](
        critic,
        """SELECT id, password
             FROM users
            WHERE name={name}""",
        name=username,
    ) as result:
        try:
            user_id, hashed = await result.one()
        except dbaccess.ZeroRowsInResult:
            raise InvalidUsername(f"No such user: `{username}`")

    if hashed is None:
        # No password set => there is no "right" password.
        logger.debug("no password set!")
        raise WrongPassword("Wrong password")

    context = createCryptContext()
    before = time.process_time()

    # ok, new_hashed = await critic.loop.run_in_executor(
    #    None, verify_and_update, password.encode(), hashed
    # )
    ok, new_hashed = context.verify_and_update(password, hashed)

    after = time.process_time()
    logger.debug("verify_and_update (outside): %.3f", after - before)

    if not ok:
        raise WrongPassword("Wrong password")

    if new_hashed:
        async with critic.database.transaction() as cursor:
            await cursor.execute(
                """UPDATE users
                      SET password={hashed_password}
                    WHERE id={user_id}""",
                hashed_password=new_hashed,
                user_id=user_id,
            )

    return await api.user.fetch(critic, user_id)


async def hashPassword(critic: api.critic.Critic, password: str) -> str:
    return createCryptContext().hash(password)


def getToken(encode: Callable[[bytes], bytes] = base64.b64encode, length: int = 20):
    return encode(os.urandom(length)).decode("ascii")


class InvalidUserName(Exception):
    pass


def validateUserName(name: str) -> None:
    if not name:
        raise InvalidUserName("Empty user name is not allowed.")
    elif not re.sub(r"\s", "", name, re.UNICODE):
        raise InvalidUserName("A user name containing only white-space is not allowed.")
    elif api.critic.settings().users.name_pattern is not None:
        if not re.match(api.critic.settings().users.name_pattern, name):
            description = api.critic.settings().users.name_pattern_description
            if isinstance(description, list):
                description = "".join(description)
            raise InvalidUserName(description)


def isValidUserName(name: str) -> bool:
    try:
        validateUserName(name)
    except InvalidUserName:
        return False
    return True


class InvalidRequest(Exception):
    pass


class Failure(Exception):
    pass


from .session import createSessionId, deleteSessionId, checkSession
from .accesscontrol import (
    AccessDenied,
    AccessControlError,
    AccessControlProfile,
    AccessControl,
)
from .database import Database
from .provider import Provider
from .oauth import OAuthProvider
from . import databases, providers

__all__ = [
    # from .session
    "createSessionId",
    "deleteSessionId",
    "checkSession",
    # from .accesscontrol
    "AccessDenied",
    "AccessControlError",
    "AccessControlProfile",
    "AccessControl",
    # from .database
    "AuthenticationError",
    "AuthenticationFailed",
    "Database",
    # from .
    "databases",
    "providers",
    # from .provider
    "Provider",
    # from .oauth
    "OAuthProvider",
]
