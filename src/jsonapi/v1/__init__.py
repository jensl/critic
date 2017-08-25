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

import configuration
import datetime

EPOCH = datetime.datetime.utcfromtimestamp(0)

def timestamp(timestamp):
    if timestamp is None:
        return None
    return (timestamp - EPOCH).total_seconds()

import users
import sessions
import repositories
import commits
import branches
import reviews
import reviewsummaries
import rebases
import changesets
import filechanges
import files
import comments
import replies
import batches
import reviewablefilechanges
import filediffs
import filecontents

if configuration.auth.ENABLE_ACCESS_TOKENS:
    import accesstokens
    import accesscontrolprofiles
    import labeledaccesscontrolprofiles

if configuration.extensions.ENABLED:
    import extensions

import documentation
