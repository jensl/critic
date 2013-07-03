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

if __name__ != "__main__":
    print >>sys.stderr, "Don't include batchprocessor.py as a module!"
    sys.exit(1)

import traceback
import time
import cStringIO

import dbaccess
import extensions.role.processchanges
import reviewing.mail

POLLING_INTERVAL = 5

# Process loop.  Terminates on any kind of error (such as if the DB connection
# is lost.)
def processLoop():
    db = dbaccess.connect()
    cursor = db.cursor()

    while True:
        cursor.execute("""SELECT DISTINCT roles.uid, batches.id
                            FROM extensionroles_processchanges AS roles
                            JOIN batches ON (batches.id > roles.skip)
                            JOIN reviewusers ON (reviewusers.review=batches.review AND reviewusers.uid=roles.uid)
                 LEFT OUTER JOIN extensionprocessedbatches AS processed ON (processed.batch=batches.id AND processed.role=roles.id)
                           WHERE processed.batch IS NULL""")

        queue = cursor.fetchall()

        if not queue:
            # Nothing to do right now; sleep a little to avoid a tight loop of
            # DB queries.  (Not that the query will be expensive at all in the
            # foreseeable future, but)

            time.sleep(POLLING_INTERVAL)
        else:
            for user_id, batch_id in queue:
                output = cStringIO.StringIO()

                extensions.role.processchanges.execute(db, user_id, batch_id, output)

                output = output.getvalue()

                if output.strip():
                    pending_mails = reviewing.mail.sendExtensionOutput(db, user_id, batch_id, output)
                    reviewing.mail.sendPendingMails(pending_mails)

# Main loop.
while True:
    try:
        try:
            processLoop()
        except KeyboardInterrupt:
            raise
        except:
            print >>sys.stderr, "".join(traceback.format_exception(*sys.exc_info()))
            time.sleep(5)
    except KeyboardInterrupt:
        break

print "exiting"
