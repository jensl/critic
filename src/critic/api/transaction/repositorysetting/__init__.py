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

_token = "[A-Za-z0-9_]+"


def validate_scope(scope: str) -> None:
    if not (1 <= len(scope) <= 64):
        raise api.repositorysetting.InvalidScope(
            "Scope must be between 1 and 64 characters long"
        )
    if not re.match(f"^{_token}$", scope):
        raise api.repositorysetting.InvalidScope(
            "Scope must contain only characters from the set [A-Za-z0-9_]"
        )


def validate_name(name: str) -> None:
    if not (1 <= len(name) <= 256):
        raise api.repositorysetting.InvalidName(
            "Name must be between 1 and 256 characters long"
        )
    if not re.match(f"^{_token}(?:\\.{_token})*$", name):
        raise api.repositorysetting.InvalidName(
            "Name must consist of '.'-separated tokens containing only "
            "characters from the set [A-Za-z0-9_]"
        )


def value_as_json(value: Any) -> str:
    try:
        return json.dumps(value)
    except TypeError as error:
        raise api.repositorysetting.Error("Value is not JSON compatible: %s" % error)
