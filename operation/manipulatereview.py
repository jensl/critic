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

import dbutils
import gitutils

import review.mail as review_mail
import mailutils

from operation import Operation, OperationResult, OperationError, Optional

class CloseReview(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)

        if review.state != "open":
            raise OperationError("review not open; can't close")
        if not review.accepted(db):
            raise OperationError("review is not accepted; can't close")

        review.close(db, user)
        review.disableTracking(db)

        db.commit()

        return OperationResult()

class DropReview(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)

        if review.state != "open":
            raise OperationError("review not open; can't drop")

        review.drop(db, user)
        review.disableTracking(db)

        db.commit()

        return OperationResult()

class ReopenReview(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)

        if review.state == "open":
            raise OperationError("review already open; can't reopen")

        review.reopen(db, user)

        db.commit()

        return OperationResult()

class PingReview(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "note": str })

    def process(self, db, user, review_id, note):
        review = dbutils.Review.fromId(db, review_id)

        cursor = db.cursor()
        cursor.execute("""SELECT DISTINCT uid
                            FROM reviewuserfiles
                            JOIN reviewfiles ON (reviewfiles.id=reviewuserfiles.file)
                            JOIN users ON (users.id=reviewuserfiles.uid)
                           WHERE reviewfiles.review=%s
                             AND reviewfiles.state='pending'
                             AND users.status!='retired'""",
                       (review.id,))

        user_ids = set([user_id for (user_id,) in cursor.fetchall()])

        # Add the pinging user and the owners (they are usually the same.)
        user_ids.add(user.id)

        for owner in review.owners: user_ids.add(owner.id)

        recipients = [dbutils.User.fromId(db, user_id) for user_id in user_ids]

        pending_mails = []
        for recipient in recipients:
            pending_mails.extend(review_mail.sendPing(db, user, recipient, recipients, review, note))
        mailutils.sendPendingMails(pending_mails)

        return OperationResult()

class UpdateReview(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "new_summary": Optional(str),
                                   "new_description": Optional(str),
                                   "new_owners": Optional([str]) })

    def process(self, db, user, review_id, new_summary=None, new_description=None, new_owners=None):
        review = dbutils.Review.fromId(db, review_id)

        if new_summary is not None:
            if not new_summary:
                raise OperationError("invalid new summary")
            review.setSummary(db, new_summary)

        if new_description is not None:
            review.setDescription(db, new_description if new_description else None)

        if new_owners is not None:
            remove_owners = set(review.owners)
            for user_name in new_owners:
                owner = dbutils.User.fromName(db, user_name)
                if owner in remove_owners: remove_owners.remove(owner)
                else: review.addOwner(db, owner)
            for owner in remove_owners:
                review.removeOwner(db, owner)

        db.commit()

        return OperationResult()
