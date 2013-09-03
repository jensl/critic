# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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

# Accepted password hash schemes.  They need to be supported by the passlib
# Python package; see http://packages.python.org/passlib for details.
PASSWORD_HASH_SCHEMES = %(installation.config.password_hash_schemes)r

# Default password hash scheme.  Must be included in PASSWORD_HASH_SCHEMES.
DEFAULT_PASSWORD_HASH_SCHEME = %(installation.config.default_password_hash_scheme)r

# (Approximate) minimum password hash time in seconds.  Higher means safer
# passwords (more difficult to decrypt using brute-force) but slower sign-in
# operation.
MINIMUM_PASSWORD_HASH_TIME = %(installation.config.minimum_password_hash_time)r

# Calibrated minimum rounds per password hash scheme.
MINIMUM_ROUNDS = %(installation.config.minimum_rounds)r
