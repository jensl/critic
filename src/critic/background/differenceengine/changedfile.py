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

from __future__ import annotations

import stat
from dataclasses import dataclass
from typing import Optional, SupportsInt, Tuple

from critic import gitaccess
from critic.diff.parse import ExamineResult
from critic.gitaccess import SHA1


Status = Tuple[ExamineResult, ExamineResult]


@dataclass
class ChangedFile:
    """Simple representation of a single changed file"""

    file_id: Optional[int]
    path: str
    old_sha1: Optional[SHA1]
    old_mode: Optional[int]
    new_sha1: Optional[SHA1]
    new_mode: Optional[int]
    status: Optional[Status] = None

    @property
    def is_added(self) -> bool:
        return self.old_sha1 is None

    @property
    def is_removed(self) -> bool:
        return self.new_sha1 is None

    def set_status(self, value: Optional[Status]) -> ChangedFile:
        if value is None:
            self.status = None
        else:
            old_lines, new_lines = value
            if self.old_mode == gitaccess.GIT_LINK_MODE:
                old_lines = None
            if self.new_mode == gitaccess.GIT_LINK_MODE:
                new_lines = None
            self.status = old_lines, new_lines
        return self

    def __int__(self) -> int:
        return self.required_file_id

    def __hash__(self) -> int:
        return hash(int(self))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, (int, ChangedFile)) and int(self) == int(other)

    @property
    def modified_regular_file(self) -> bool:
        """True if not added or removed, and a regular file on both sides"""
        return (
            self.old_sha1 != self.new_sha1
            and self.old_mode is not None
            and self.new_mode is not None
            and stat.S_ISREG(self.old_mode | self.new_mode)
        )

    @property
    def required_file_id(self) -> int:
        assert self.file_id is not None
        return self.file_id

    @property
    def required_old_sha1(self) -> SHA1:
        assert self.old_sha1 is not None
        return self.old_sha1

    @property
    def required_old_mode(self) -> int:
        assert self.old_mode is not None
        return self.old_mode

    @property
    def required_new_sha1(self) -> SHA1:
        assert self.new_sha1 is not None
        return self.new_sha1

    @property
    def required_new_mode(self) -> int:
        assert self.new_mode is not None
        return self.new_mode

    @property
    def required_status(self) -> Status:
        assert self.status is not None
        return self.status
