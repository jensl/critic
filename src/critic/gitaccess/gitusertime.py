# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

import datetime
import logging
import re

logger = logging.getLogger(__name__)

from . import GitError

RE_VALUE = re.compile(r"^(.*?)\s+<(.*?)>\s+(\d+)\s+(\+|-)(\d\d)(\d\d)$")


class GitUserTime:
    def __init__(self, value: str) -> None:
        match = RE_VALUE.match(value)
        if not match:
            raise GitError("Malformed Git user metadata: %r" % value)
        self.name, self.email, timestamp, sign, hours, minutes = match.groups()

        utcoffset = datetime.timedelta(
            hours=int(hours, base=10), minutes=int(minutes, base=10)
        )
        if sign == "-":
            utcoffset *= -1
        timezone = datetime.timezone(utcoffset)

        self.time = datetime.datetime.fromtimestamp(int(timestamp, base=10), timezone)

    def __str__(self) -> str:
        return (
            f"{self.name} <{self.email}> {int(self.time.timestamp())} "
            f"{self.time.strftime('%z')}"
        )
