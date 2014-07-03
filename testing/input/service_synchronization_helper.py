# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 Jens Lindström, Opera Software ASA
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

import sys
import os
import time

pidfile_path, signal, timeout = sys.argv[1:]

with open(pidfile_path) as pidfile:
    pid = int(pidfile.read().strip())

with open(pidfile_path + ".busy", "w"):
    pass

os.kill(pid, int(signal))

deadline = time.time() + int(timeout)

while os.path.isfile(pidfile_path + ".busy"):
    if time.time() > deadline:
        sys.exit(1)
    time.sleep(0.01)
