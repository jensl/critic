# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

from passlib.context import CryptContext

import configuration

class CheckFailed(Exception): pass
class NoSuchUser(CheckFailed): pass
class WrongPassword(CheckFailed): pass

def createCryptContext():
    kwargs = {}

    for scheme, min_rounds in configuration.auth.MINIMUM_ROUNDS.items():
        kwargs["%s__min_rounds" % scheme] = min_rounds

    all_schemes = configuration.auth.PASSWORD_HASH_SCHEMES
    default_scheme = configuration.auth.DEFAULT_PASSWORD_HASH_SCHEME

    return CryptContext(
        schemes=all_schemes, default=default_scheme,
        deprecated=filter(lambda scheme: scheme != default_scheme, all_schemes),
        **kwargs)

def checkPassword(db, username, password):
    cursor = db.cursor()
    cursor.execute("SELECT password FROM users WHERE name=%s", (username,))

    row = cursor.fetchone()
    if not row:
        raise NoSuchUser
    hashed = row[0]

    ok, new_hashed = createCryptContext().verify_and_update(password, hashed)

    if not ok:
        raise WrongPassword

    if new_hashed:
        cursor.execute("UPDATE users SET password=%s WHERE name=%s",
                       (new_hashed, username))

def hashPassword(password):
    return createCryptContext().encrypt(password)
