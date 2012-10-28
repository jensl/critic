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
import socket

def service(name, address=0, script=0, pidfile_path=0, logfile_path=0, loglevel=0):
    if address      == 0: address      = os.path.join(configuration.paths.SOCKETS_DIR, name + ".unix")
    if script       == 0: script       = os.path.join("background", name + ".py")
    if pidfile_path == 0: pidfile_path = os.path.join(configuration.paths.RUN_DIR, name + ".pid")
    if logfile_path == 0: logfile_path = os.path.join(configuration.paths.LOG_DIR, name + ".log")
    if loglevel     == 0: loglevel     = "info"

    return { "name": name,
             "address": address,
             "script": script,
             "pidfile_path": pidfile_path,
             "logfile_path": logfile_path,
             "loglevel": loglevel }

HIGHLIGHT         = service(name="highlight")
CHANGESET         = service(name="changeset")
GITHOOK           = service(name="githook")
BRANCHTRACKER     = service(name="branchtracker",     address=None)
BRANCHTRACKERHOOK = service(name="branchtrackerhook", address=(configuration.base.HOSTNAME, 9999))
MAILDELIVERY      = service(name="maildelivery",      address=None)
WATCHDOG          = service(name="watchdog",          address=None)
SERVICEMANAGER    = service(name="servicemanager")

HIGHLIGHT["cache_dir"] = os.path.join(configuration.paths.CACHE_DIR, "highlight")
HIGHLIGHT["min_context_length"] = 5
HIGHLIGHT["max_context_length"] = 256
HIGHLIGHT["max_workers"] = 4

CHANGESET["max_workers"] = 4
CHANGESET["rss_limit"] = 1024 ** 3

WATCHDOG["rss_soft_limit"] = 1024 ** 3
WATCHDOG["rss_hard_limit"] = 2 * WATCHDOG["rss_soft_limit"]

SERVICEMANAGER["services"] = [HIGHLIGHT,
                              CHANGESET,
                              GITHOOK,
                              BRANCHTRACKER,
                              BRANCHTRACKERHOOK,
                              MAILDELIVERY,
                              WATCHDOG]
