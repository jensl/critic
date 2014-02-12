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

import configuration
import os.path

# Whether extension support is enabled.  If False, the rest of the
# configuration in this file is irrelevant.
ENABLED = %(installation.extensions.enabled)s

# Where to search for system extensions.
SYSTEM_EXTENSIONS_DIR = os.path.join(configuration.paths.DATA_DIR, "extensions")

# Name of directory under users' $HOME in which to search for user extensions.
# If set to None, user extensions support is disabled.
USER_EXTENSIONS_DIR = "CriticExtensions"

FLAVORS = {
    "js/v8":
        { "executable": "%(installation.extensions.critic_v8_jsshell)s",
          "library": os.path.join(configuration.paths.INSTALL_DIR, "library", "js", "v8") }
    }

DEFAULT_FLAVOR = "%(installation.extensions.default_flavor)s"

# Directory into which extension version snapshots are installed.
INSTALL_DIR = os.path.join(configuration.paths.DATA_DIR, "extension-snapshots")

# Directory into which extension repository work copies are created.
WORKCOPY_DIR = os.path.join(configuration.paths.DATA_DIR, "temporary", "EXTENSIONS")

# Long timeout, in seconds.  Used for extension "Page" roles.
LONG_TIMEOUT = 300
# Short timeout, in seconds.  Used for all other roles.
SHORT_TIMEOUT = 5
