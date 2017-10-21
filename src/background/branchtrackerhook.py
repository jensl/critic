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
import signal
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import dbutils
from textutils import json_encode, json_decode

if "--wait-for-update" in sys.argv:
    data = json_decode(sys.stdin.read())

    branch_id = data["branch_id"]
    timeout = data["timeout"]
    log_offset = data["log_offset"]

    db = dbutils.Database.forSystem()

    cursor = db.cursor()
    cursor.execute("SELECT MAX(time) FROM trackedbranchlog WHERE branch=%s", (branch_id,))
    last_log_entry = cursor.fetchone()[0]

    start = time.time()

    status = None
    output = ""

    while time.time() - start < timeout:
        time.sleep(0.5)

        db.commit()

        cursor = db.cursor()
        cursor.execute("SELECT hook_output FROM trackedbranchlog WHERE branch=%s ORDER BY time ASC OFFSET %s", (branch_id, log_offset))
        rows = cursor.fetchall()

        if rows:
            for (hook_output,) in rows: output += hook_output
            status = "output"
            break

        cursor.execute("SELECT updating FROM trackedbranches WHERE id=%s", (branch_id,))

        if not cursor.fetchone()[0]:
            # Update performed, but no log entries added.
            status = "no-output"
            break
    else:
        status = "timeout"

    sys.stdout.write(json_encode({ "status": status, "output": output or None }))
    sys.stdout.flush()

    db.close()
else:
    import configuration

    from background.utils import PeerServer
    from textutils import json_decode
    from subprocess import STDOUT

    class BranchTrackerHook(PeerServer):
        class WaitForUpdate(PeerServer.ChildProcess):
            def __init__(self, client, branch_id, timeout, log_offset):
                super(BranchTrackerHook.WaitForUpdate, self).__init__(client.server, [sys.executable, sys.argv[0], "--wait-for-update"], stderr=STDOUT)
                self.client = client
                self.client.write("wait\n")
                self.write(json_encode({ "branch_id": branch_id, "timeout": timeout, "log_offset": log_offset }))
                self.close()

            def handle_input(self, _file, data):
                try: data = json_decode(data)
                except ValueError:
                    self.server.error("invalid response from wait-for-update child: %r" % data)
                    self.client.close()

                if data["status"] == "output":
                    self.client.write(data["output"])
                    self.server.debug("  hook output written to client")
                elif data["status"] == "no-output":
                    self.server.debug("  update produced no hook output")
                else:
                    self.server.debug("  timeout")

                self.client.close()

        class Client(PeerServer.SocketPeer):
            def __init__(self, server, peersocket, peeraddress):
                super(BranchTrackerHook.Client, self).__init__(server, peersocket)
                self.__peeraddress = peeraddress

            def handle_input(self, _file, data):
                try: data = json_decode(data)
                except ValueError: return

                message = "connection from %s:%d:" % self.__peeraddress
                message += "\n  repository: %s" % data["repository"]

                if "timeout" in data:
                    message += "\n  timeout:    %d" % data["timeout"]
                if data["branches"]:
                    message += "\n  branches:   %s" % ", ".join(data["branches"])
                if data["tags"]:
                    message += "\n  tags:       %s" % ", ".join(data["tags"])

                self.server.info(message)

                db = dbutils.Database.forSystem()

                try:
                    cursor = db.cursor()
                    notify_tracker = False
                    wait_for_reply = False

                    # Make sure the 'knownremotes' table has this remote listed
                    # as "pushing" since it obviously is.

                    cursor.execute("""SELECT pushing
                                        FROM knownremotes
                                       WHERE url=%s""",
                                   (data["repository"],))

                    row = cursor.fetchone()

                    if not row:
                        cursor.execute("""INSERT INTO knownremotes (url, pushing)
                                               VALUES (%s, TRUE)""",
                                       (data["repository"],))
                    elif not row[0]:
                        cursor.execute("""UPDATE knownremotes
                                             SET pushing=TRUE
                                           WHERE url=%s""",
                                       (data["repository"],))

                    # If we just recorded this remote as "pushing," adjust the
                    # configured updating frequency of any existing tracked
                    # branches from it.

                    if not row or not row[0]:
                        cursor.execute("""UPDATE trackedbranches
                                             SET delay='1 week'
                                           WHERE remote=%s""",
                                       (data["repository"],))

                    for branch in data["branches"]:
                        cursor.execute("""SELECT id, local_name
                                            FROM trackedbranches
                                           WHERE remote=%s
                                             AND remote_name=%s
                                             AND NOT disabled
                                             AND next IS NOT NULL""",
                                       (data["repository"], branch))

                        row = cursor.fetchone()
                        if row:
                            branch_id, local_name = row

                            cursor.execute("""UPDATE trackedbranches
                                                 SET next=NULL
                                               WHERE id=%s""",
                                           (branch_id,))

                            notify_tracker = True
                            self.server.debug("tracked branch: %s" % local_name)

                            if len(data["branches"]) == 1 and local_name.startswith("r/"):
                                wait_for_reply = (True, branch_id)
                                self.server.debug("  will wait for reply")

                    if data["tags"]:
                        cursor.execute("""SELECT id
                                            FROM trackedbranches
                                           WHERE remote=%s
                                             AND remote_name=%s
                                             AND NOT disabled
                                             AND next IS NOT NULL""",
                                       (data["repository"], "*"))

                        row = cursor.fetchone()
                        if row:
                            branch_id = row[0]

                            cursor.execute("""UPDATE trackedbranches
                                                 SET next=NULL
                                               WHERE id=%s""",
                                           (branch_id,))

                            notify_tracker = True

                    db.commit()

                    if notify_tracker:
                        if wait_for_reply:
                            branch_id = wait_for_reply[1]
                            cursor.execute("SELECT COUNT(*) FROM trackedbranchlog WHERE branch=%s", (branch_id,))
                            log_offset = cursor.fetchone()[0]
                            self.server.add_peer(BranchTrackerHook.WaitForUpdate(self, branch_id, data.get("timeout", 30), log_offset))

                        try:
                            branchtracker_pid = int(open(configuration.services.BRANCHTRACKER["pidfile_path"]).read().strip())
                            os.kill(branchtracker_pid, signal.SIGHUP)
                        except:
                            self.server.exception()
                            return

                        if wait_for_reply:
                            return

                    self.close()
                finally:
                    try: db.close()
                    except: pass

        def __init__(self):
            super(BranchTrackerHook, self).__init__(service=configuration.services.BRANCHTRACKERHOOK)

        def handle_peer(self, peersocket, peeraddress):
            return BranchTrackerHook.Client(self, peersocket, peeraddress)

    server = BranchTrackerHook()
    sys.exit(server.start())
