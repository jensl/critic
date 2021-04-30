# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import json
import re
from typing import Any

from critic import api


def valueAsJSON(value: Any) -> str:
    try:
        return json.dumps(value)
    except TypeError as error:
        raise api.setting.Error(f"Value is not JSON compatible: {error}")


def validate_setting(scope: str, name: str) -> None:
    if not (1 <= len(scope) <= 64):
        raise api.setting.InvalidScope(
            "Scope must be between 1 and 64 characters long"
        )
    if not re.match("^[A-Za-z0-9_]+$", scope):
        raise api.setting.InvalidScope(
            "Scope must contain only characters from the set [A-Za-z0-9_]"
        )

    if not (1 <= len(name) <= 256):
        raise api.setting.InvalidName(
            "Name must be between 1 and 256 characters long"
        )
    if not re.match(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*$", name):
        raise api.setting.InvalidName(
            "Name must consist of '.'-separated tokens containing only "
            "characters from the set [A-Za-z0-9_]"
        )
