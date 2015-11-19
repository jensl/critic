# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import configuration
import dbutils
import background.utils
import extensions.role.filterhook

class ExtensionTasks(background.utils.BackgroundProcess):
    def __init__(self):
        service = configuration.services.EXTENSIONTASKS

        super(ExtensionTasks, self).__init__(service=service)

    def run(self):
        if not configuration.extensions.ENABLED:
            self.info("service stopping: extension support not enabled")
            return

        failed_events = set()

        while not self.terminated:
            self.interrupted = False

            with dbutils.Database.forSystem() as db:
                cursor = db.cursor()
                cursor.execute("""SELECT id
                                    FROM extensionfilterhookevents
                                ORDER BY id ASC""")

                finished_events = []

                for (event_id,) in cursor:
                    if event_id not in failed_events:
                        try:
                            extensions.role.filterhook.processFilterHookEvent(
                                db, event_id, self.debug)
                        except Exception:
                            self.exception()
                            failed_events.add(event_id)
                        else:
                            finished_events.append(event_id)

                cursor.execute("""DELETE FROM extensionfilterhookevents
                                        WHERE id=ANY (%s)""",
                               (finished_events,))

                db.commit()

            timeout = self.run_maintenance()

            if timeout is None:
                timeout = 86400

            self.debug("sleeping %d seconds" % timeout)

            self.signal_idle_state()

            before = time.time()

            time.sleep(timeout)

            if self.interrupted:
                self.debug("sleep interrupted after %.2f seconds"
                           % (time.time() - before))

def start_service():
    extensiontasks = ExtensionTasks()
    return extensiontasks.start()

background.utils.call("extensiontasks", start_service)
