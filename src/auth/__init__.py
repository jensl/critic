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

import os
import base64
import re

import configuration
import dbutils

class CheckFailed(Exception): pass
class NoSuchUser(CheckFailed): pass
class WrongPassword(CheckFailed): pass

def createCryptContext():
    try:
        from passlib.context import CryptContext
    except ImportError:
        if not configuration.debug.IS_QUICKSTART:
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

    kwargs = {}

    for scheme, min_rounds in configuration.auth.MINIMUM_ROUNDS.items():
        kwargs["%s__min_rounds" % scheme] = min_rounds

    all_schemes = configuration.auth.PASSWORD_HASH_SCHEMES
    default_scheme = configuration.auth.DEFAULT_PASSWORD_HASH_SCHEME

    return CryptContext(
        schemes=all_schemes, default=default_scheme,
        deprecated=[scheme for scheme in all_schemes
                    if scheme != default_scheme],
        **kwargs)

def checkPassword(db, username, password):
    cursor = db.cursor()
    cursor.execute("SELECT id, password FROM users WHERE name=%s", (username,))

    row = cursor.fetchone()
    if not row:
        raise NoSuchUser
    user_id, hashed = row

    if hashed is None:
        # No password set => there is no "right" password.
        raise WrongPassword

    ok, new_hashed = createCryptContext().verify_and_update(password, hashed)

    if not ok:
        raise WrongPassword

    if new_hashed:
        with db.updating_cursor("users") as cursor:
            cursor.execute("UPDATE users SET password=%s WHERE id=%s",
                           (new_hashed, user_id))

    return dbutils.User.fromId(db, user_id)

def hashPassword(password):
    return createCryptContext().encrypt(password)

def getToken(encode=base64.b64encode, length=20):
    return encode(os.urandom(length))

class InvalidUserName(Exception): pass

def validateUserName(name):
    if not name:
        raise InvalidUserName("Empty user name is not allowed.")
    elif not re.sub(r"\s", "", name, re.UNICODE):
        raise InvalidUserName(
            "A user name containing only white-space is not allowed.")
    elif configuration.base.USER_NAME_PATTERN is not None:
        if not re.match(configuration.base.USER_NAME_PATTERN, name):
            raise InvalidUserName(
                configuration.base.USER_NAME_PATTERN_DESCRIPTION)

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

from .accesscontrol import (AccessDenied, AccessControlError,
                           AccessControlProfile, AccessControl)
from .database import AuthenticationError, AuthenticationFailed, Database

DATABASE = None

from . import databases

from .provider import Provider
from .oauth import OAuthProvider

PROVIDERS = {}

from . import providers
