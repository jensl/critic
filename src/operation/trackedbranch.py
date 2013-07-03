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

from operation import Operation, OperationResult, OperationFailure, OperationError, Optional

import dbutils
import gitutils
import htmlutils
import configuration

import calendar
import os
import signal

def getTrackedBranchReviewState(db, branch_id):
    cursor = db.cursor()
    cursor.execute("""SELECT reviews.state
                        FROM reviews
                        JOIN branches ON (branches.id=reviews.branch)
                        JOIN trackedbranches ON (trackedbranches.repository=branches.repository
                                             AND trackedbranches.local_name=branches.name)
                       WHERE trackedbranches.id=%s""",
                   (branch_id,))

    row = cursor.fetchone()
    return row[0] if row else None

class TrackedBranchLog(Operation):
    def __init__(self):
        Operation.__init__(self, { "branch_id": int })

    def process(self, db, user, branch_id):
        cursor = db.cursor()
        cursor.execute("""SELECT previous, next
                            FROM trackedbranches
                           WHERE id=%s""",
                       (branch_id,))

        previous, next = cursor.fetchone()
        previous = calendar.timegm(previous.utctimetuple()) if previous else None
        next = calendar.timegm(next.utctimetuple()) if next else None

        cursor.execute("""SELECT time, from_sha1, to_sha1, hook_output, successful
                            FROM trackedbranchlog
                           WHERE branch=%s
                        ORDER BY time ASC""",
                       (branch_id,))

        items = []

        for update_time, from_sha1, to_sha1, hook_output, successful in cursor:
            items.append({ "time": calendar.timegm(update_time.utctimetuple()),
                           "from_sha1": from_sha1,
                           "to_sha1": to_sha1,
                           "hook_output": hook_output,
                           "successful": successful })

        cursor.execute("""SELECT repository
                            FROM trackedbranches
                           WHERE id=%s""",
                       (branch_id,))

        repository = gitutils.Repository.fromId(db, cursor.fetchone()[0])

        return OperationResult(previous=previous,
                               next=next,
                               items=items,
                               repository={ "id": repository.id, "name": repository.name })

class DisableTrackedBranch(Operation):
    def __init__(self):
        Operation.__init__(self, { "branch_id": int })

    def process(self, db, user, branch_id):
        cursor = db.cursor()

        if not user.hasRole(db, "administrator"):
            cursor.execute("""SELECT 1
                                FROM trackedbranchusers
                               WHERE branch=%s
                                 AND uid=%s""",
                           (branch_id, user.id))

            if not cursor.fetchone():
                raise OperationFailure(code="notallowed",
                                       title="Not allowed!",
                                       message="Operation not permitted.")

        cursor.execute("""UPDATE trackedbranches
                             SET disabled=TRUE
                           WHERE id=%s""",
                       (branch_id,))

        db.commit()

        return OperationResult()

class TriggerTrackedBranchUpdate(Operation):
    def __init__(self):
        Operation.__init__(self, { "branch_id": int })

    def process(self, db, user, branch_id):
        cursor = db.cursor()

        if not user.hasRole(db, "administrator"):
            cursor.execute("""SELECT 1
                                FROM trackedbranchusers
                               WHERE branch=%s
                                 AND uid=%s""",
                           (branch_id, user.id))

            if not cursor.fetchone():
                raise OperationFailure(code="notallowed",
                                       title="Not allowed!",
                                       message="Operation not permitted.")

        review_state = getTrackedBranchReviewState(db, branch_id)
        if review_state is not None and review_state != "open":
            raise OperationFailure(code="reviewnotopen",
                                   title="The review is not open!",
                                   message="You need to reopen the review before new commits can be added to it.")

        cursor.execute("""UPDATE trackedbranches
                             SET next=NULL
                           WHERE id=%s""",
                       (branch_id,))

        db.commit()

        pid = int(open(configuration.services.BRANCHTRACKER["pidfile_path"]).read().strip())
        os.kill(pid, signal.SIGHUP)

        return OperationResult()

class EnableTrackedBranch(Operation):
    def __init__(self):
        Operation.__init__(self, { "branch_id": int,
                                   "new_remote_name": Optional(str) })

    def process(self, db, user, branch_id, new_remote_name=None):
        cursor = db.cursor()

        if not user.hasRole(db, "administrator"):
            cursor.execute("""SELECT 1
                                FROM trackedbranchusers
                               WHERE branch=%s
                                 AND uid=%s""",
                           (branch_id, user.id))

            if not cursor.fetchone():
                raise OperationFailure(code="notallowed",
                                       title="Not allowed!",
                                       message="Operation not permitted.")

        review_state = getTrackedBranchReviewState(db, branch_id)
        if review_state is not None and review_state != "open":
            raise OperationFailure(code="reviewnotopen",
                                   title="The review is not open!",
                                   message="You need to reopen the review before new commits can be added to it.")

        if new_remote_name is not None:
            cursor.execute("""SELECT remote
                                FROM trackedbranches
                               WHERE id=%s""",
                           (branch_id,))

            remote = cursor.fetchone()[0]

            if not gitutils.Repository.lsremote(remote, pattern="refs/heads/" + new_remote_name):
                raise OperationFailure(
                    code="refnotfound",
                    title="Remote ref not found!",
                    message=("Could not find the ref <code>%s</code> in the repository <code>%s</code>."
                             % (htmlutils.htmlify("refs/heads/" + new_remote_name),
                                htmlutils.htmlify(remote))),
                    is_html=True)

            cursor.execute("""UPDATE trackedbranches
                                 SET remote_name=%s,
                                     disabled=FALSE,
                                     next=NULL
                               WHERE id=%s""",
                           (new_remote_name, branch_id))
        else:
            cursor.execute("""UPDATE trackedbranches
                                 SET disabled=FALSE,
                                     next=NULL
                               WHERE id=%s""",
                           (branch_id,))

        db.commit()

        pid = int(open(configuration.services.BRANCHTRACKER["pidfile_path"]).read().strip())
        os.kill(pid, signal.SIGHUP)

        return OperationResult()

class DeleteTrackedBranch(Operation):
    def __init__(self):
        Operation.__init__(self, { "branch_id": int })

    def process(self, db, user, branch_id):
        cursor = db.cursor()

        if not user.hasRole(db, "administrator"):
            cursor.execute("""SELECT 1
                                FROM trackedbranchusers
                               WHERE branch=%s
                                 AND uid=%s""",
                           (branch_id, user.id))

            if not cursor.fetchone():
                raise OperationFailure(code="notallowed",
                                       title="Not allowed!",
                                       message="Operation not permitted.")

        cursor.execute("""DELETE FROM trackedbranches
                                WHERE id=%s""",
                       (branch_id,))

        db.commit()

        return OperationResult()

class AddTrackedBranch(Operation):
    def __init__(self):
        Operation.__init__(self, { "repository_id": int,
                                   "source_location": str,
                                   "source_name": str,
                                   "target_name": str,
                                   "users": [str] })

    def process(self, db, user, repository_id, source_location, source_name, target_name, users):
        cursor = db.cursor()
        cursor.execute("""SELECT 1
                            FROM trackedbranches
                           WHERE repository=%s
                             AND local_name=%s""",
                       (repository_id, target_name))

        if cursor.fetchone():
            raise OperationError, "branch '%s' already tracks another branch" % target_name

        users = [dbutils.User.fromName(db, username) for username in users]
        forced = True

        if target_name.startswith("r/"):
            cursor.execute("""SELECT 1
                                FROM reviews
                                JOIN branches ON (branches.id=reviews.branch)
                               WHERE branches.repository=%s
                                 AND branches.name=%s""",
                           (repository_id, target_name))

            if not cursor.fetchone():
                raise OperationError, "non-existing review branch can't track another branch"
        else:
            forced = False

        cursor.execute("""SELECT 1
                            FROM knownremotes
                           WHERE url=%s
                             AND pushing""",
                       (source_location,))

        if cursor.fetchone():
            delay = "1 week"
        else:
            delay = "1 hour"

        cursor.execute("""INSERT INTO trackedbranches (repository, local_name, remote, remote_name, forced, delay)
                               VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id""",
                       (repository_id, target_name, source_location, source_name, forced, delay))

        branch_id = cursor.fetchone()[0]

        for user in users:
            cursor.execute("""INSERT INTO trackedbranchusers (branch, uid)
                                   VALUES (%s, %s)""",
                           (branch_id, user.id))

        db.commit()

        pid = int(open(configuration.services.BRANCHTRACKER["pidfile_path"]).read().strip())
        os.kill(pid, signal.SIGHUP)

        return OperationResult()
