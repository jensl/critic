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

__doc__ = "Installation utilities."

import os
import sys

quiet = False
is_quick_start = False

root_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

sys.path.insert(0, os.path.join(root_dir, "src"))

# Helpers.
from . import input
from . import process
from . import utils

# Modules.
from . import prereqs
from . import system
from . import paths
from . import files
from . import database
from . import smtp
from . import config
from . import httpd
from . import criticctl
from . import admin
from . import initd
from . import prefs
from . import git
from . import migrate
from . import extensions

modules = [prereqs,
           system,
           paths,
           files,
           database,
           extensions,
           config,
           httpd,
           criticctl,
           admin,
           smtp,
           initd,
           git,
           migrate,
           prefs]
