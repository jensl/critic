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

# Directory where system configuration is stored.
CONFIG_DIR = os.path.join("%(installation.paths.etc_dir)s", configuration.base.SYSTEM_IDENTITY)

# Directory where the main system is installed.
INSTALL_DIR = "%(installation.paths.install_dir)s"

# Directory under which data files of a more permanent nature are
# stored.
DATA_DIR = "%(installation.paths.data_dir)s"

# Directory under which cache files that can be discarded at any time
# are stored.
CACHE_DIR = os.path.join("%(installation.paths.cache_dir)s", configuration.base.SYSTEM_IDENTITY)

# Directory in which log files are stored.
LOG_DIR = os.path.join("%(installation.paths.log_dir)s", configuration.base.SYSTEM_IDENTITY)

# Directory in which pid files are stored.
RUN_DIR = os.path.join("%(installation.paths.run_dir)s", configuration.base.SYSTEM_IDENTITY)

# Directory in which WSGI daemon process pid files are stored.
WSGI_PIDFILE_DIR = os.path.join(RUN_DIR, "wsgi")

# Directory in which Unix socket files are created.
SOCKETS_DIR = os.path.join(RUN_DIR, "sockets")

# Directory where the main (public) git repositories are stored.
GIT_DIR = "%(installation.paths.git_dir)s"

# Directory in which emails are stored pending delivery.
OUTBOX = os.path.join(DATA_DIR, "outbox")
