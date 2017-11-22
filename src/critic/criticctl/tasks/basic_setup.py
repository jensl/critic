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

import logging
import subprocess

logger = logging.getLogger(__name__)

name = "basic_setup"
description = "Basic system setup"


def setup(parser):
    from critic import base

    identity = parser.get_default("configuration")["system.identity"]

    paths_group = parser.add_argument_group(
        "Installation locations",
        description=(
            "By default, Critic installs in system-wide locations "
            "following the Linux Filesystem Hierarchy Standard. These "
            "default locations can be overridden en mass using the "
            "--prefix option, which puts everything under a single "
            "directory, unless in turn overridden by the specific "
            "argmuents."
        ),
    )

    paths_group.add_argument(
        "--prefix", help="Directory under which all installed files are stored."
    )

    paths_group.add_argument(
        "--settings-dir",
        help="Directory where the basic system configuration is installed.",
    )
    paths_group.add_argument(
        "--executables-dir", help="Directory where executables are installed."
    )
    paths_group.add_argument(
        "--data-dir", help="Directory where persistent data files are installed."
    )
    paths_group.add_argument(
        "--cache-dir", help="Directory where Critic's temporary data files are created."
    )
    paths_group.add_argument(
        "--repositories-dir", help="Directory where Git repositories are created."
    )
    paths_group.add_argument(
        "--logs-dir", help="Directory where Critic's log files are created."
    )
    paths_group.add_argument(
        "--runtime-dir",
        help=(
            "Directory where Critic creates runtime files such as PID files "
            "and UNIX sockets."
        ),
    )
