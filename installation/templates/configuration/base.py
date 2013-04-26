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

# The name of the system identity which this configuration applies to.
SYSTEM_IDENTITY = "main"

# True if this is a development installation of the system; False if
# it is a production installation.  (Cosmetic effects only.)
IS_DEVELOPMENT = %(installation.system.is_development)r

# The name of the system user that Critic runs as.
SYSTEM_USER_NAME = "%(installation.system.username)s"

# The email address to use in the "Sender:" header in all generated
# emails, and in the "From:" header in emails unless there's a real
# user whose email address it makes sense to use instead.
SYSTEM_USER_EMAIL = "%(installation.system.email)s"

# The name of the system group that Critic runs as.
SYSTEM_GROUP_NAME = "%(installation.system.groupname)s"

ADMINISTRATORS = [{ "name": "%(installation.admin.username)s",
                    "email": "%(installation.admin.email)s",
                    "fullname": "%(installation.admin.fullname)s" }]

# The primary FQDN of the server.  This is used when generating
# message IDs for emails, and should *not* be different in different
# system identities, since then email threading will not work
# properly.
HOSTNAME = "%(installation.system.hostname)s"

# The way Critic identifies/authenticates users: "host" or "critic"
AUTHENTICATION_MODE = "%(installation.config.auth_mode)s"

# If AUTHENTICATION_MODE="critic", type of session: "httpauth" or "cookie"
SESSION_TYPE = "%(installation.config.session_type)s"

# If AUTHENTICATION_MODE="critic" and SESSION_TYPE="cookie", maximum
# age of session in seconds.  Zero means no maximum age; session is
# valid until user logs out.
SESSION_MAX_AGE = 0

# Allow (restricted) anonymous access to the system.  Only supported if
# AUTHENTICATION_MODE="critic" and SESSION_TYPE="cookie".
ALLOW_ANONYMOUS_USER = %(installation.config.allow_anonymous_user)r

# Access scheme: "http", "https" or "both".
ACCESS_SCHEME = "%(installation.config.access_scheme)s"
