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
ENABLED = False

# Where to search for extensions.
SEARCH_ROOT = "/home"

# Directory where the Javascript extension library is installed.
JS_LIBRARY_DIR = os.path.join(configuration.paths.INSTALL_DIR, "library", "js")

# Directory into which extension version snapshots are installed.
INSTALL_DIR = os.path.join(configuration.paths.DATA_DIR, "extensions")
