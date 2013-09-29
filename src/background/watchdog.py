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
import multiprocessing

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
            else: raise Exception("unknown unit: %s" % words[2])
            return int(words[1]) * unit
    else: raise Exception("invalid pid")

class Watchdog(BackgroundProcess):
    def __init__(self):
        service = configuration.services.WATCHDOG

        super(Watchdog, self).__init__(service=service)

        cpu_count = multiprocessing.cpu_count()

        self.load1_limit = service.get("load1_limit", 0) * cpu_count
        self.load5_limit = service.get("load5_limit", 0) * cpu_count
        self.load15_limit = service.get("load15_limit", 0) * cpu_count

    def run(self):
        soft_restart_attempted = set()
        previous = {}

        getloadavg_failed = False
        load1_has_warned = 0
        load1_last_time = 0
        load5_has_warned = 0
        load5_last_time = 0
        load15_has_warned = 0
        load15_last_time = 0

        while not self.terminated:
            self.interrupted = False

            def sendLoadAverageWarning(interval, limit, load):
                cpu_count = multiprocessing.cpu_count()
                sendAdministratorMessage("watchdog", "%d-minute load average" % interval,
                                         ("The current %d-minute load average is %.2f!\n" % (interval, load)) +
                                         ("The configured limit is %.2f (%.2f x %d CPUs).\n" % (limit, limit / cpu_count, cpu_count)) +
                                         "\n" +
                                         "-- critic\n")

            try:
                load1, load5, load15 = os.getloadavg()
                self.debug("load average: %r, %r, %r" % (load1, load5, load15))
            except OSError:
                load1, load5, load15 = 0, 0, 0

                if not getloadavg_failed:
                    self.exception("failed to detect system load average")
                    getloadavg_failed = True

            now = time.time()

            if self.load1_limit and load1 > self.load1_limit:
                if load1 > load1_has_warned * 1.2 or now - load1_last_time > 60:
                    sendLoadAverageWarning(1, self.load1_limit, load1)
                    load1_has_warned = load1
                    load1_last_time = now
            else:
                load1_has_warned = 0
                load1_last_time = 0

                if self.load5_limit and load5 > self.load5_limit:
                    if load5 > load5_has_warned * 1.2 or now - load5_last_time > 5 * 60:
                        sendLoadAverageWarning(5, self.load5_limit, load5)
                        load5_has_warned = load5
                        load5_last_time = now
                else:
                    load5_has_warned = 0
                    load5_last_time = 0

                    if self.load15_limit and load15 > self.load15_limit:
                        if load15 > load15_has_warned * 1.2 or now - load15_last_time > 15 * 60:
                            sendLoadAverageWarning(15, self.load15_limit, load15)
                            load15_has_warned = load15
                            load15_last_time = now
                    else:
                        load15_has_warned = 0
                        load15_last_time = 0

            pidfile_dir = configuration.paths.WSGI_PIDFILE_DIR

            if os.path.isdir(pidfile_dir):
                pids = set(map(int, os.listdir(pidfile_dir)))
            else:
                pids = set()

            for pid in pids:
                try: rss = getRSS(pid)
                except IOError as error:
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
