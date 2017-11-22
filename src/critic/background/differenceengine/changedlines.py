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

from dataclasses import dataclass
from typing import Sequence, TypeVar

T = TypeVar("T")


@dataclass
class ChangedLines:
    """Simple representation of a single block of changed lines"""

    index: int
    offset: int
    delete_offset: int
    delete_count: int
    delete_length: int
    insert_offset: int
    insert_count: int
    insert_length: int

    def extract_old_lines(self, lines: Sequence[T]) -> Sequence[T]:
        assert self.delete_length
        assert self.delete_offset + self.delete_length <= len(lines)
        return lines[self.delete_offset : self.delete_offset + self.delete_length]

    def extract_new_lines(self, lines: Sequence[T]) -> Sequence[T]:
        assert self.insert_length
        assert self.insert_offset + self.insert_length <= len(lines)
        return lines[self.insert_offset : self.insert_offset + self.insert_length]
