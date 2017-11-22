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

import asyncio
import datetime
from typing import Optional, Union, Callable, Awaitable, cast, overload

EPOCH = datetime.datetime.fromtimestamp(0)
EPOCH_UTC = datetime.datetime.fromtimestamp(0, datetime.timezone.utc)


Timestamp = Union[
    datetime.datetime, Awaitable[datetime.datetime],
]
OptionalTimestamp = Union[
    Optional[datetime.datetime], Awaitable[Optional[datetime.datetime]],
]


@overload
async def timestamp(timestamp: Timestamp) -> float:
    ...


@overload
async def timestamp(timestamp: OptionalTimestamp) -> Optional[float]:
    ...


async def timestamp(timestamp: OptionalTimestamp) -> Optional[float]:
    if timestamp and not isinstance(timestamp, datetime.datetime):
        timestamp = await timestamp
    if timestamp is None:
        return None
    assert isinstance(timestamp, datetime.datetime)
    if timestamp.tzinfo:
        return (timestamp - EPOCH_UTC).total_seconds()
    return (timestamp - EPOCH).total_seconds()


from . import accesscontrolprofiles
from . import accesstokens
from . import batches
from . import branches
from . import branchsettings
from . import branchupdates
from . import changesets
from . import comments
from . import commits
from . import extensions
from . import extensionversions
from . import extensioninstallations
from . import externalaccounts
from . import filechanges
from . import filecontents
from . import filediffs
from . import files
from . import labeledaccesscontrolprofiles
from . import mergeanalyses
from . import rebases
from . import replies
from . import repositories
from . import repositoryfilters
from . import repositorysettings
from . import reviewablefilechanges
from . import reviewevents
from . import reviewintegrationrequests
from . import reviewfilters
from . import reviewpings
from . import reviews
from . import reviewscopes
from . import reviewscopefilters
from . import reviewtags
from . import sessions
from . import systemevents
from . import systemsettings
from . import trackedbranches
from . import trees
from . import tutorials
from . import useremails
from . import users
from . import usersettings
from . import usersshkeys

from . import documentation

__all__ = [
    "accesscontrolprofiles",
    "accesstokens",
    "batches",
    "branches",
    "branchsettings",
    "branchupdates",
    "changesets",
    "comments",
    "commits",
    "extensions",
    "extensionversions",
    "extensioninstallations",
    "externalaccounts",
    "filechanges",
    "filecontents",
    "filediffs",
    "files",
    "labeledaccesscontrolprofiles",
    "mergeanalyses",
    "rebases",
    "replies",
    "repositories",
    "repositoryfilters",
    "repositorysettings",
    "reviewablefilechanges",
    "reviewevents",
    "reviewintegrationrequests",
    "reviewfilters",
    "reviewpings",
    "reviews",
    "reviewscopes",
    "reviewscopefilters",
    "reviewtags",
    "sessions",
    "systemevents",
    "systemsettings",
    "trackedbranches",
    "trees",
    "tutorials",
    "useremails",
    "users",
    "usersettings",
    "usersshkeys",
    "documentation",
]
