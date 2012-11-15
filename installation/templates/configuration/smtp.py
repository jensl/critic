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

HOST = %(installation.smtp.host)r
PORT = %(installation.smtp.port)r
USERNAME = %(installation.smtp.username)r
PASSWORD = %(installation.smtp.password)r
USE_SSL = %(installation.smtp.use_ssl)r
USE_STARTTLS = %(installation.smtp.use_starttls)r

MAX_ATTEMPTS = 10
