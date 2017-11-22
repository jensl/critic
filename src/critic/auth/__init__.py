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

    def __init__(self, *args, field_name=None):
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


def createCryptContext():
    settings = api.critic.settings().authentication.databases.internal

    try:
        from passlib.context import CryptContext
    except ImportError:
        if not settings.system.is_quickstart:
            raise

        # Support quick-starting without 'passlib' installed by falling back to
        # completely bogus unsalted SHA-256-based hashing.

        import hashlib

        class CryptContext:
            def __init__(self, **kwargs):
                pass

            def encrypt(self, password):
                return hashlib.sha256(password).hexdigest()

            def verify_and_update(self, password, hashed):
                return self.encrypt(password) == hashed, None

    kwargs = {f"{settings.used_scheme}__min_rounds": settings.minimum_rounds}

    return CryptContext(
        schemes=settings.accepted_schemes,
        default=settings.used_scheme,
        deprecated=[
            scheme
            for scheme in settings.accepted_schemes
            if scheme != settings.used_scheme
        ],
        **kwargs,
    )


async def checkPassword(critic, username, password):
    async with critic.query(
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
        raise WrongPassword("Wrong password")

    context = createCryptContext()

    def verify_and_update(password, hashed):
        before = time.time()
        ok, new_hashed = context.verify_and_update(password, hashed)
        after = time.time()
        logger.debug("verify_and_update (inside): %.3f", after - before)
        return ok, new_hashed

    before = time.process_time()

    # ok, new_hashed = await critic.loop.run_in_executor(
    #    None, verify_and_update, password.encode(), hashed
    # )
    ok, new_hashed = context.verify_and_update(password.encode(), hashed)

    after = time.process_time()
    logger.debug("verify_and_update (outside): %.3f", after - before)

    if not ok:
        raise WrongPassword("Wrong password")

    if new_hashed:
        async with critic.database.transaction("users") as cursor:
            await cursor.execute(
                """UPDATE users
                      SET password={hashed_password}
                    WHERE id={user_id}""",
                hashed_password=new_hashed,
                user_id=user_id,
            )

    return await api.user.fetch(critic, user_id)


async def hashPassword(critic, password):
    context = createCryptContext()
    # return await critic.loop.run_in_executor(None, context.encrypt, password.encode())
    return context.encrypt(password.encode())


def getToken(encode=base64.b64encode, length=20):
    return encode(os.urandom(length)).decode("ascii")


class InvalidUserName(Exception):
    pass


def validateUserName(name):
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


def isValidUserName(name):
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
