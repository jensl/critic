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
import os.path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import configuration

from dbutils import Database
from textutils import json_decode, json_encode

if "--json-job" in sys.argv[1:]:
    from resource import getrlimit, setrlimit, RLIMIT_RSS
    from traceback import print_exc

    soft_limit, hard_limit = getrlimit(RLIMIT_RSS)
    rss_limit = configuration.services.CHANGESET["rss_limit"]
    if soft_limit < rss_limit:
        setrlimit(RLIMIT_RSS, (rss_limit, hard_limit))

    from changeset.create import createChangeset

    request = json_decode(sys.stdin.read())

    try:
        db = Database()

        createChangeset(db, request)

        db.close()

        sys.stdout.write(json_encode(request))
    except:
        print "Request:"
        print json_encode(request, indent=2)
        print

        print_exc(file=sys.stdout)
else:
    from background.utils import JSONJobServer

    def describeRequest(request):
        if request["changeset_type"] in ("direct", "merge", "conflicts"):
            return "%s (%s)" % (request["changeset_type"], request["child_sha1"][:8])
        else:
            return "custom (%s..%s)" % (request["parent_sha1"][:8], request["child_sha1"][:8])

    class ChangesetServer(JSONJobServer):
        def __init__(self):
            service = configuration.services.CHANGESET

            super(ChangesetServer, self).__init__(service)

            if "purge_at" in service:
                hour, minute = service["purge_at"]
                self.register_maintenance(hour=hour, minute=minute, callback=self.__purge)

        def execute_command(self, client, command):
            if command["command"] == "purge":
                purged_count = self.__purge()

                client.write(json_encode({ "status": "ok",
                                           "purged": purged_count }))
                client.close()
            else:
                super(ChangesetServer, self).execute_command(client, command)

        def request_started(self, job, request):
            super(ChangesetServer, self).request_started(job, request)

            self.debug("started: %s in %s [pid=%d]" % (describeRequest(request), request["repository_name"], job.pid))

        def request_finished(self, job, request, result):
            super(ChangesetServer, self).request_finished(job, request, result)

            if "error" not in result:
                for parent_sha1, changeset_id in result["changeset_ids"].items():
                    self.info("finished: %d for %s (%s..%s) in %s [pid=%d]"
                              % (changeset_id, request["changeset_type"],
                                 parent_sha1[:8], request["child_sha1"][:8],
                                 request["repository_name"], job.pid))

        def __purge(self):
            db = Database()
            cursor = db.cursor()

            cursor.execute("""SELECT COUNT(*)
                                FROM changesets
                                JOIN customchangesets ON (customchangesets.changeset=changesets.id)
                               WHERE time < NOW() - INTERVAL '3 months'""")
            npurged = cursor.fetchone()[0]

            if npurged:
                self.info("purging %d old custom changesets" % npurged)

                cursor.execute("DELETE FROM changesets USING customchangesets WHERE id=changeset AND time < NOW() - INTERVAL '3 months'")
                db.commit()

            db.close()

            return npurged

    server = ChangesetServer()
    server.run()
