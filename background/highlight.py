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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

if "--json-job" in sys.argv[1:]:
    from syntaxhighlight.generate import generateHighlight
    from background.utils import json_decode, json_encode

    request = json_decode(sys.stdin.read())

    request["highlighted"] = generateHighlight(repository_path=request["repository_path"],
                                               sha1=request["sha1"],
                                               language=request["language"])

    sys.stdout.write(json_encode(request))
else:
    from background.utils import JSONJobServer
    from syntaxhighlight.context import importCodeContexts

    import configuration
    import dbutils

    class HighlightServer(JSONJobServer):
        def __init__(self):
            super(HighlightServer, self).__init__(service=configuration.services.HIGHLIGHT)

            self.db = dbutils.Database()

            self.register_maintenance(hour=3, minute=15, callback=self.__compact)

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

        def __compact(self):
            import syntaxhighlight

            now = time.time()

            max_age_uncompressed = 7 * 24 * 60 * 60
            max_age_compressed = 90 * 24 * 60 * 60

            uncompressed_count = 0
            compressed_count = 0

            purged_paths = []

            db = dbutils.Database()
            cursor = db.cursor()

            cursor.execute("CREATE TEMPORARY TABLE purged (sha1 CHAR(40) PRIMARY KEY)")

            cache_path = configuration.services.HIGHLIGHT["cache_dir"]

            for section in sorted(os.listdir(cache_path)):
                if len(section) == 2:
                    for filename in os.listdir("%s/%s" % (cache_path, section)):
                        fullname = "%s/%s/%s" % (cache_path, section, filename)
                        age = now - os.stat(fullname).st_mtime

                        if len(filename) > 38 and filename[38] == "." and filename[39:] in syntaxhighlight.LANGUAGES:
                            if age > max_age_uncompressed:
                                self.debug("compressing: %s/%s" % (section, filename))
                                worker = process(["/bin/bzip2", fullname])
                                worker.wait()
                                compressed_count += 1
                            else:
                                uncompressed_count += 1
                        elif len(filename) > 42 and filename[38] == "." and filename[-4] == "." and filename[39:-4] in syntaxhighlight.LANGUAGES:
                            if filename.endswith(".bz2"):
                                if age > max_age_compressed:
                                    self.debug("purging: %s/%s" % (section, filename))
                                    cursor.execute("INSERT INTO purged (sha1) VALUES (%s)", (section + filename[:-4],))
                                    purged_paths.append(fullname)
                                else:
                                    compressed_count += 1
                            elif filename.endswith(".ctx"):
                                self.debug("deleting context file: %s/%s" % (section, filename))
                                os.unlink(fullname)

            self.debug("uncompressed=%d / compressed=%d / purged=%d" % (uncompressed_count, compressed_count, len(purged_paths)))

            if purged_paths:
                for path in purged_paths: os.unlink(path)
                cursor.execute("DELETE FROM codecontexts USING purged WHERE codecontexts.sha1=purged.sha1")

            db.commit()
            db.close()

    server = HighlightServer()
    server.run()
