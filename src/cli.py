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
import traceback

import dbutils
import gitutils
import mailutils
import reviewing.utils
import reviewing.filters
import reviewing.mail
import reviewing.comment
import reviewing.comment.propagate

from textutils import json_encode, json_decode

db = None

def init():
    global db

    db = dbutils.Database.forSystem()

def finish():
    global db

    if db:
        db.commit()
        db.close()
        db = None

def abort():
    global db

    if db:
        db.rollback()
        db.close()
        db = None

def sendCustomMail(from_user, recipients, subject, headers, body, review):
    assert recipients is not None or review is not None

    if review:
        if recipients is None:
            recipients = review.getRecipients(db)

    files = []

    for to_user in recipients:
        if not to_user.getPreference(db, "email.activated") \
               or to_user.status == "retired":
            continue

        if review:
            parent_message_id = reviewing.mail.getReviewMessageId(
                db, to_user, review, files)

        message_id = mailutils.generateMessageId(len(files) + 1)

        if review:
            filename = reviewing.mail.sendMail(
                db, review, message_id, from_user, to_user, recipients, subject,
                body, parent_message_id, headers)
        else:
            filename = mailutils.queueMail(
                from_user, to_user, recipients, subject, body,
                message_id=message_id, headers=headers)

        files.append(filename)

    return files

def propagateComment(data):
    try:
        review = dbutils.Review.fromId(db, data["review_id"])
        commit = gitutils.Commit.fromId(db, review.repository, data["commit_id"])
        propagation = reviewing.comment.propagate.Propagation(db)
        if "chain_id" in data:
            chain = reviewing.comment.CommentChain.fromId(
                db, data["chain_id"], user=None, review=review)
            if chain is None:
                return "invalid chain id"
            if commit != chain.addressed_by:
                return "wrong commit: must be current addressed_by"
            propagation.setExisting(
                review, chain.id, commit, data["file_id"],
                data["first_line"], data["last_line"], True)
            commits = review.getCommitSet(db).without(commit.parents)
            propagation.calculateAdditionalLines(
                commits, review.branch.getHead(db))
        else:
            if not propagation.setCustom(
                    review, commit, data["file_id"],
                    data["first_line"], data["last_line"]):
                return "invalid location"
            propagation.calculateInitialLines()
        data = {
            "status": "clean" if propagation.active else "modified",
            "lines": [[sha1, first_line, last_line]
                      for sha1, (first_line, last_line)
                      in propagation.new_lines.items()]
            }
        if not propagation.active:
            data["addressed_by"] = propagation.addressed_by[0].child.getId(db)
        return data
    except dbutils.NoSuchReview:
        return "invalid review id"
    except gitutils.GitReferenceError:
        return "invalid commit id"
    except Exception as exception:
        return str(exception)

HANDLERS = { "propagate-comment": propagateComment }

try:
    if len(sys.argv) > 1:
        init()

        for command in sys.argv[1:]:
            pending_mails = None

            if command == "generate-mails-for-batch":
                data = json_decode(sys.stdin.readline())
                batch_id = data["batch_id"]
                was_accepted = data["was_accepted"]
                is_accepted = data["is_accepted"]
                pending_mails = reviewing.utils.generateMailsForBatch(db, batch_id, was_accepted, is_accepted)
            elif command == "generate-mails-for-assignments-transaction":
                data = json_decode(sys.stdin.readline())
                transaction_id = data["transaction_id"]
                pending_mails = reviewing.utils.generateMailsForAssignmentsTransaction(db, transaction_id)
            elif command == "apply-filters":
                data = json_decode(sys.stdin.readline())
                filters = reviewing.filters.Filters()
                user = dbutils.User.fromId(db, data["user_id"]) if "user_id" in data else None
                if "review_id" in data:
                    review = dbutils.Review.fromId(db, data["review_id"])
                    filters.setFiles(db, review=review)
                    filters.load(db, review=review, user=user,
                                 added_review_filters=data.get("added_review_filters", []),
                                 removed_review_filters=data.get("removed_review_filters", []))
                else:
                    repository = gitutils.Repository.fromId(db, data["repository_id"])
                    filters.setFiles(db, file_ids=data["file_ids"])
                    filters.load(db, repository=repository, recursive=data.get("recursive", False), user=user)
                sys.stdout.write(json_encode(filters.data) + "\n")
            elif command == "generate-custom-mails":
                pending_mails = []
                for data in json_decode(sys.stdin.readline()):
                    from_user = dbutils.User.fromId(db, data["sender"])
                    if data.get("recipients"):
                        recipients = [dbutils.User.fromId(db, user_id)
                                      for user_id in data["recipients"]]
                    else:
                        recipients = None
                    subject = data["subject"]
                    headers = data.get("headers")
                    body = data["body"]
                    if "review_id" in data:
                        review = dbutils.Review.fromId(db, data["review_id"])
                    else:
                        review = None
                    pending_mails.extend(sendCustomMail(
                        from_user, recipients, subject, headers, body, review))
            elif command == "set-review-state":
                data = json_decode(sys.stdin.readline())
                error = ""
                try:
                    user = dbutils.User.fromId(db, data["user_id"])
                    review = dbutils.Review.fromId(db, data["review_id"])
                    if review.state != data["old_state"]:
                        error = "invalid old state"
                    elif data["new_state"] == "open":
                        review.reopen(db, user)
                    elif data["new_state"] == "closed":
                        review.close(db, user)
                    elif data["new_state"] == "dropped":
                        review.drop(db, user)
                    else:
                        error = "invalid new state"
                except dbutils.NoSuchUser:
                    error = "invalid user id"
                except dbutils.NoSuchReview:
                    error = "invalid review id"
                except Exception as error:
                    error = str(error)
                sys.stdout.write(error + "\n")
            elif command in HANDLERS:
                data_in = json_decode(sys.stdin.readline())
                data_out = HANDLERS[command](data_in)
                sys.stdout.write(json_encode(data_out) + "\n")
            else:
                sys.stdout.write(json_encode("unknown command: %s" % command) + "\n")
                sys.exit(0)

            if pending_mails is not None:
                sys.stdout.write(json_encode(pending_mails) + "\n")

        finish()
except Exception:
    sys.stdout.write(json_encode(traceback.format_exc()) + "\n")
finally:
    abort()
