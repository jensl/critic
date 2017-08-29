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
import time
from subprocess import Popen as process

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import background.utils
from textutils import json_decode, json_encode

if "--json-job" in sys.argv[1:]:
    def perform_job():
        import syntaxhighlight.generate

        request = json_decode(sys.stdin.read())
        request["highlighted"] = syntaxhighlight.generate.generateHighlight(
            repository_path=request["repository_path"],
            sha1=request["sha1"],
            language=request["language"],
            mode=request["mode"])
        sys.stdout.write(json_encode(request))

    background.utils.call("highlight_job", perform_job)
else:
    import background.utils
    from syntaxhighlight import isHighlighted
    from syntaxhighlight.context import importCodeContexts

    import configuration
    import dbutils

    class HighlightServer(background.utils.JSONJobServer):
        def __init__(self):
            service = configuration.services.HIGHLIGHT

            super(HighlightServer, self).__init__(service)

            self.db = dbutils.Database.forSystem()

            if "compact_at" in service:
                hour, minute = service["compact_at"]
                self.register_maintenance(hour=hour, minute=minute, callback=self.__compact)

        def request_result(self, request):
            if isHighlighted(request["sha1"], request["language"], request["mode"]):
                result = request.copy()
                result["highlighted"] = True
                return result

        def request_started(self, job, request):
            super(HighlightServer, self).request_started(job, request)

            self.debug("started: %s:%s (%s) in %s [pid=%d]" % (request["path"], request["sha1"][:8], request["language"], request["repository_path"], job.pid))

        def request_finished(self, job, request, result):
            super(HighlightServer, self).request_finished(job, request, result)

            failed = "" if "error" not in result else " (failed!)"
            self.info("finished: %s:%s (%s) in %s [pid=%d]%s" % (request["path"], request["sha1"][:8], request["language"], request["repository_path"], job.pid, failed))

            ncontexts = importCodeContexts(self.db, request["sha1"], request["language"])

            if ncontexts: self.debug("  added %d code contexts" % ncontexts)
            else: self.debug("  no code contexts added")

        def execute_command(self, client, command):
            if command["command"] == "compact":
                uncompressed_count, compressed_count, purged_files_count, purged_contexts_count = self.__compact()

                client.write(json_encode({ "status": "ok",
                                           "uncompressed": uncompressed_count,
                                           "compressed": compressed_count,
                                           "purged_files": purged_files_count,
                                           "purged_contexts": purged_contexts_count }))
                client.close()
            else:
                super(HighlightServer, self).execute_command(client, command)

        def __compact(self):
            import syntaxhighlight

            cache_dir = configuration.services.HIGHLIGHT["cache_dir"]

            if not os.path.isdir(cache_dir):
                # Newly installed system that hasn't highlighted anything.
                return 0, 0, 0, 0

            self.info("cache compacting started")

            now = time.time()

            max_age_uncompressed = 7 * 24 * 60 * 60
            max_age_compressed = 90 * 24 * 60 * 60

            uncompressed_count = 0
            compressed_count = 0

            purged_paths = []

            db = dbutils.Database.forSystem()

            cursor = db.cursor()

            cursor.execute("CREATE TEMPORARY TABLE purged (sha1 CHAR(40) PRIMARY KEY)")
            cursor.execute("INSERT INTO purged (sha1) SELECT DISTINCT sha1 FROM codecontexts")

            for section in sorted(os.listdir(cache_dir)):
                if len(section) == 2:
                    for filename in os.listdir("%s/%s" % (cache_dir, section)):
                        fullname = "%s/%s/%s" % (cache_dir, section, filename)
                        age = now - os.stat(fullname).st_mtime

                        parts = filename.split(".")

                        if len(parts) < 2 \
                                or len(parts[0]) != 38 \
                                or parts[1] not in syntaxhighlight.LANGUAGES:
                            os.unlink(fullname)
                            continue

                        sha1 = section + parts[0]

                        if parts[-1] == "bz2":
                            if age > max_age_compressed:
                                self.debug("purging: %s/%s" % (section, filename))
                                purged_paths.append(fullname)
                            else:
                                cursor.execute("DELETE FROM purged WHERE sha1=%s", (sha1,))
                                compressed_count += 1
                        elif parts[-1] == "ctx":
                            self.debug("deleting context file: %s/%s" % (section, filename))
                            os.unlink(fullname)
                        else:
                            cursor.execute("DELETE FROM purged WHERE sha1=%s", (sha1,))
                            if age > max_age_uncompressed:
                                self.debug("compressing: %s/%s" % (section, filename))
                                worker = process(["/bin/bzip2", fullname])
                                worker.wait()
                                compressed_count += 1
                            else:
                                uncompressed_count += 1

            self.info("cache compacting finished: uncompressed=%d / compressed=%d / purged=%d"
                      % (uncompressed_count, compressed_count, len(purged_paths)))

            if purged_paths:
                for path in purged_paths: os.unlink(path)

            cursor.execute("SELECT COUNT(*) FROM purged")

            purged_contexts = cursor.fetchone()[0]

            cursor.execute("""DELETE
                                FROM codecontexts
                               WHERE sha1 IN (SELECT sha1
                                                FROM purged)""")

            db.commit()
            db.close()

            return uncompressed_count, compressed_count, len(purged_paths), purged_contexts

    def start_service():
        server = HighlightServer()
        return server.start()

    background.utils.call("highlight", start_service)
