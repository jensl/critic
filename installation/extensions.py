# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

def prepare(mode, arguments, data):
    data["installation.extensions.enabled"] = False
    data["installation.extensions.critic_v8_jsshell"] = "NOT_INSTALLED"
    data["installation.extensions.default_flavor"] = "js/v8"

    if mode == "upgrade":
        import configuration
        data["installation.extensions.enabled"] = \
            configuration.extensions.ENABLED
        try:
            data["installation.extensions.critic_v8_jsshell"] = \
                configuration.extensions.FLAVORS["js/v8"]["executable"]
        except (KeyError, AttributeError):
            pass
        try:
            data["installation.extensions.default_flavor"] = \
                configuration.extensions.DEFAULT_FLAVOR
        except AttributeError:
            pass

    return True
