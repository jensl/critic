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
import yaml


def load_json(filename: str) -> object:
    import pkg_resources

    return json.load(pkg_resources.resource_stream(__name__, filename))


def load_yaml(filename: str) -> object:
    import pkg_resources

    return yaml.safe_load(pkg_resources.resource_stream(__name__, filename))


def load(filename: str) -> str:
    import pkg_resources

    return pkg_resources.resource_string(__name__, filename).decode()
