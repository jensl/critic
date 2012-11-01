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

import sys
import os
import os.path
import time
import signal
import errno

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import configuration

from background.utils import BackgroundProcess
from mailutils import sendAdministratorMessage

def getRSS(pid):
    for line in open("/proc/%d/status" % pid):
        words = line.split()
        if words[0] == "VmRSS:":
            if words[2].lower() == "kb": unit = 1024
            elif words[2].lower() == "mb": unit = 1024 ** 2
            elif words[2].lower() == "gb": unit = 1024 ** 3
            else: raise Exception, "unknown unit: %s" % words[2]
            return int(words[1]) * unit
    else: raise Exception, "invalid pid"

class Watchdog(BackgroundProcess):
    def __init__(self):
        super(Watchdog, self).__init__(service=configuration.services.WATCHDOG)

    def run(self):
        soft_restart_attempted = set()
        previous = {}

        while not self.terminated:
            self.interrupted = False

            pidfile_dir = configuration.paths.WSGI_PIDFILE_DIR

            if os.path.isdir(pidfile_dir):
                pids = set(map(int, os.listdir(pidfile_dir)))
            else:
                pids = []

            for pid in pids:
                try: rss = getRSS(pid)
                except IOError, error:
                    if error.errno == errno.ENOENT:
                        self.warning("unlinking stale pid-file: %s" % os.path.join(pidfile_dir, str(pid)))
                        os.unlink(os.path.join(pidfile_dir, str(pid)))
                        continue
                    else: raise

                if previous.get(pid) != rss:
                    self.debug("pid=%d, rss=%d bytes" % (pid, rss))
                    previous[pid] = rss

                if rss > configuration.services.WATCHDOG["rss_hard_limit"]:
                    sendAdministratorMessage("watchdog", "pid(%d): hard memory limit exceeded" % pid,
                                             ("Current RSS: %d kilobytes\nSending process SIGKILL (%d).\n\n-- critic"
                                              % (rss, signal.SIGKILL)))
                    self.info("Killing pid(%d): hard memory limit exceeded, RSS: %d kilobytes" % (pid, rss))
                    os.kill(pid, signal.SIGKILL)
                elif rss > configuration.services.WATCHDOG["rss_soft_limit"] and pid not in soft_restart_attempted:
                    sendAdministratorMessage("watchdog", "pid(%d): soft memory limit exceeded" % pid,
                                             ("Current RSS: %d kilobytes\nSending process SIGINT (%d).\n\n"
                                              % (rss, signal.SIGINT)))
                    self.info("Killing pid(%d): soft memory limit exceeded, RSS: %d kilobytes" % (pid, rss))
                    os.kill(pid, signal.SIGINT)
                    soft_restart_attempted.add(pid)

            for pid in previous.keys():
                if pid not in pids: del previous[pid]

            soft_restart_attempted = soft_restart_attempted & pids

            time.sleep(10)

watchdog = Watchdog()
watchdog.run()
