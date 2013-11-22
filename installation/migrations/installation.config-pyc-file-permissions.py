# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Martin Olsson
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

import os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--uid", type=int)
parser.add_argument("--gid", type=int)

arguments = parser.parse_args()

os.setgid(arguments.gid)
os.setuid(arguments.uid)

import configuration

config_dir = os.path.dirname(configuration.__file__)
for entry in os.listdir(config_dir):
    if entry.endswith(".py"):
        if entry.startswith("_") and os.path.exists(os.path.join(config_dir, entry[1:])):
            # If the upgrade modifies a configuration file, say file.py, it
            # will keep a backup of the file stored as _file.py (also in the
            # configuration directory) and there won't be a pyc file for the
            # backup, so skip ahead to avoid unnecessarily printing the below warning.
            continue
        config_file = os.path.join(config_dir, entry)
        pyc_file = config_file + "c"
        try:
            os.chmod(pyc_file, os.stat(config_file).st_mode)
        except Exception as e:
            print("WARNING: installation.config-pyc-file-permissions.py "
                  "failed to restrict file permissions for '%s'. Please make "
                  "sure all .pyc files in the Critic configuration directory "
                  "exists, belongs to critic:critic and are chmod'd similar "
                  "to the corresponding .py file. The specific error "
                  "reported was: %s" % (pyc_file, e))
