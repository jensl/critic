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

import os.path

import installation
from installation import process

def prepare(arguments):
    return True

def execute():
    process.check_call(["sudo", "-u", installation.system.username, "PYTHONPATH=%s" % os.path.join(installation.paths.etc_dir, "main"), installation.prereqs.python, "maintenance/installpreferences.py"])
    return True

def undo():
    pass
