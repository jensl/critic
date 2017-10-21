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

from . import users
from . import sessions
from . import repositories
from . import commits
from . import branches
from . import branchupdates
from . import reviews
from . import reviewsummaries
from . import rebases
from . import changesets
from . import filechanges
from . import files
from . import comments
from . import replies
from . import batches
from . import reviewablefilechanges
from . import filediffs
from . import filecontents

if configuration.auth.ENABLE_ACCESS_TOKENS:
    from . import accesstokens
    from . import accesscontrolprofiles
    from . import labeledaccesscontrolprofiles

if configuration.extensions.ENABLED:
    from . import extensions

from . import documentation
