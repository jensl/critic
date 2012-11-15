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

import bcrypt

class CheckFailed(Exception): pass
class NoSuchUser(CheckFailed): pass
class WrongPassword(CheckFailed): pass

def checkPassword(db, username, password):
    cursor = db.cursor()
    cursor.execute("SELECT password FROM users WHERE name=%s", (username,))

    try: hashed = cursor.fetchone()[0]
    except: raise NoSuchUser

    if bcrypt.hashpw(password, hashed) == hashed: return
    else: raise WrongPassword

def hashPassword(password):
    return bcrypt.hashpw(password, bcrypt.gensalt())
