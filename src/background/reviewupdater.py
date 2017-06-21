# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import argparse
import json
import subprocess
import sys
import traceback

import configuration
import api
import dbutils
import gitutils
import background.utils
import mailutils

def process_branchupdate(db, review, branchupdate_id, pendingrefupdate_id):
    if pendingrefupdate_id is None:
        updater_id = None
    else:
        cursor = db.readonly_cursor()
        cursor.execute("""SELECT updater
                            FROM pendingrefupdates
                           WHERE id=%s""",
                       (pendingrefupdate_id,))
        updater_id, = cursor.fetchone()

    result = {
        "status": "ok"
    }

    try:
        review.processBranchUpdate(
            db, branchupdate_id, pendingrefupdate_id)

        next_state = 'finished'
    except dbutils.ReviewUpdateError as error:
        gitutils.emitGitHookOutput(
            db, pendingrefupdate_id,
            # FIXME: Refine this error message.
            #output="An error occurred while updating the review.",
            output=traceback.format_exc(),
            error=error.message)

        if updater_id is not None:
            updater = dbutils.User.fromId(db, updater_id)
            is_developer = updater.hasRole(db, "developer")

            if not is_developer:
                summary = ("r/%d: processing branch update failed"
                           % review.id)
                mailutils.sendAdministratorErrorReport(
                    db, "reviewupdater", summary, error.message)

        result.update({
            "status": "error",
            "error": str(error),
        })

        next_state = 'failed'

    with db.updating_cursor("pendingrefupdates") as cursor:
        cursor.execute(
            """UPDATE pendingrefupdates
                  SET state=%s
                WHERE id=%s""",
            (next_state, pendingrefupdate_id))

    return result

def run_slave0():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slave", action="store_true")
    parser.add_argument("--review_id", required=True, type=int)
    parser.add_argument("--branchupdate_id", type=int)
    parser.add_argument("--pendingrefupdate_id", type=int)

    arguments = parser.parse_args()

    review_id = arguments.review_id
    branchupdate_id = arguments.branchupdate_id
    pendingrefupdate_id = arguments.pendingrefupdate_id

    db = api.critic.startSession(for_system=True).database

    try:
        review = dbutils.Review.fromId(db, review_id)

        if branchupdate_id is not None:
            result = process_branchupdate(
                db, review, branchupdate_id, pendingrefupdate_id)
    finally:
        db.close()

    return result

def run_slave():
    try:
        result = run_slave0()
    except Exception:
        result = {
            "status": "error",
            "error": traceback.format_exc(),
        }
    print json.dumps(result)

class ReviewUpdaterSlave(background.utils.PeerServer.ChildProcess):
    def __init__(self, server, review_id, branchupdate_id=None,
                 pendingrefupdate_id=None):
        args = [
            sys.executable, "-m", "background.reviewupdater",
            "--slave",
            "--review_id=%d" % review_id
        ]
        if branchupdate_id:
            args.append("--branchupdate_id=%d" % branchupdate_id)
            if pendingrefupdate_id is not None:
                args.append("--pendingrefupdate_id=%d" % pendingrefupdate_id)
        super(ReviewUpdaterSlave, self).__init__(
            server, args, stderr=subprocess.STDOUT)
        self.__review_id = review_id
        self.__branchupdate_id = branchupdate_id
        self.close()

    def handle_input(self, _file, data):
        try:
            result = json.loads(data)
        except ValueError:
            result = {
                "status": "error",
                "error": "invalid output from slave process"
            }
        self.server.finished(
            self.__review_id, self.__branchupdate_id, result)

class ReviewUpdater(background.utils.PeerServer):
    def __init__(self):
        service = configuration.services.REVIEWUPDATER
        super(ReviewUpdater, self).__init__(service)

        self.__processing = set()

    def wakeup(self):
        db = dbutils.Database()

        try:
            cursor = db.readonly_cursor()
            cursor.execute(
                """SELECT reviews.id, branchupdates.id, pendingrefupdates.id
                     FROM branchupdates
                     JOIN branches ON (branches.id=branchupdates.branch)
                     JOIN reviews ON (reviews.branch=branches.id)
          LEFT OUTER JOIN reviewupdates ON (reviewupdates.branchupdate=branchupdates.id)
          LEFT OUTER JOIN pendingrefupdates ON (pendingrefupdates.repository=branches.repository
                                            AND pendingrefupdates.name=('refs/heads/' || branches.name))
                    WHERE reviewupdates.review IS NULL
                      AND (pendingrefupdates.id IS NULL
                        OR pendingrefupdates.state='processed')""")

            for review_id, branchupdate_id, pendingrefupdate_id in cursor.fetchall():
                if branchupdate_id not in self.__processing:
                    self.debug("Processing update: r/%d (branchupdate=%d) ..."
                               % (review_id, branchupdate_id))

                    self.add_peer(ReviewUpdaterSlave(
                        self, review_id, branchupdate_id=branchupdate_id,
                        pendingrefupdate_id=pendingrefupdate_id))
                    self.__processing.add(branchupdate_id)

        finally:
            db.close()

    def finished(self, review_id, branchupdate_id, result):
        if result["status"] == "error":
            self.error("Failed to process update: r/%d (branchupdate=%r):\n\n%s"
                       % (review_id, branchupdate_id, result["error"].strip()))
        else:
            if branchupdate_id is not None:
                self.__processing.remove(branchupdate_id)

            self.info("Processed update: r/%d (branchupdate=%r)"
                      % (review_id, branchupdate_id))

def start_service():
    review_updater = ReviewUpdater()
    return review_updater.start()

if "--slave" in sys.argv:
    background.utils.call("reviewupdater", run_slave)
else:
    background.utils.call("reviewupdater", start_service)
