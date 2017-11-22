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

import distutils.spawn
import logging
import subprocess

logger = logging.getLogger(__name__)

SYSTEMCTL = None


def _require_systemctl():
    from . import fail

    global SYSTEMCTL
    SYSTEMCTL = distutils.spawn.find_executable("systemctl")
    if not SYSTEMCTL:
        fail("Could not find `systemctl` executable in $PATH!")


def check():
    _require_systemctl()


def run(command, *args):
    _require_systemctl()
    return subprocess.check_output([SYSTEMCTL, command] + list(args))


def start_service(service_name):
    run("restart", service_name)
    logger.info("Started service: %s", service_name)


def restart_service(service_name):
    run("restart", service_name)
    logger.info("Restarted service: %s", service_name)


def stop_service(service_name):
    run("stop", service_name)
    logger.info("Stopped service: %s", service_name)


def daemon_reload():
    run("daemon-reload")
    logger.info("Reloaded systemd daemon")
