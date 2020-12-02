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

import json
from typing import Any, List, Tuple, Union


class Error(object):
    def __init__(self, traceback: str):
        self.traceback = traceback


KeyItem = Union[int, str, tuple]
Key = Tuple[KeyItem, ...]


def serialize_key(key: Key) -> str:
    return json.dumps(key)


def deserialize_key(serialized: str) -> Key:
    def tuples(value: Union[int, str, List[Any]]) -> KeyItem:
        if isinstance(value, list):
            return tuple(tuples(item) for item in value)
        return value

    return tuple(tuples(item) for item in json.loads(serialized))
