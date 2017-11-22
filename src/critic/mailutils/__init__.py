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

import json
import os
import time
import errno

from email.utils import parseaddr

from critic import api
from critic import base
from critic import dbutils


def generateMessageId(index=1):
    now = time.time()

    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime(now))
    timestamp_ms = "%04d" % ((now * 10000) % 10000)

    return "%s.%s.%04d" % (timestamp, timestamp_ms, index)


class User:
    def __init__(self, name, fullname, email):
        self.name = name
        self.fullname = fullname
        self.email = email


class Mail(object):
    def __init__(self, recipient, message_id, filename):
        self.recipient = recipient
        self.message_id = message_id
        self.filename = filename


def queueMail(
    from_user,
    to_user,
    recipients,
    subject,
    body,
    *,
    message_id=None,
    parent_message_id=None,
    headers=None
):
    if not message_id:
        message_id = generateMessageId()

    if headers is None:
        headers = {}
    else:
        headers = headers.copy()

    if parent_message_id:
        parent_message_id = "<%s@%s>" % (
            parent_message_id,
            api.critic.settings().system.hostname,
        )

    outbox_dir = os.path.join(base.configuration()["paths.home"], "outbox")

    try:
        os.makedirs(outbox_dir)
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise

    filename = "%s/%s_%s_%s.txt.pending" % (
        outbox_dir,
        from_user.name,
        to_user.name,
        message_id,
    )

    def user_json(value):
        if isinstance(value, (User, api.user.User)):
            return {"fullname": value.fullname, "email": value.email}
        fullname, email = parseaddr(value)
        return {"fullname": fullname, "email": email}

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(
            {
                "message_id": message_id,
                "parent_message_id": parent_message_id,
                "headers": headers,
                "time": time.time(),
                "from_user": user_json(from_user),
                "to_user": user_json(to_user),
                "recipients": [user_json(recipient) for recipient in recipients],
                "subject": subject,
                "body": body,
            },
            file,
        )

    return Mail(to_user, message_id, filename)


def sendMessage(recipients, subject, body, headers=None):
    from_user = User(
        base.configuration()["system.username"],
        "Critic System",
        api.critic.getSystemEmail(),
    )
    mails = []

    for to_user in recipients:
        if isinstance(to_user, str):
            fullname, email = parseaddr(to_user)
            name, _, _ = email.partition("@")
            name, _, _ = email.partition("+")
            to_user = User(name, fullname, email)

        mails.append(
            queueMail(from_user, to_user, recipients, subject, body, headers=headers)
        )

    sendPendingMails(mails)

    return mails


def sendAdministratorMessage(source, summary, message):
    recipients = []

    for recipient in api.critic.settings().system.recipients:
        recipients.append(recipient)

    sendMessage(recipients, "%s: %s" % (source, summary), message)


def sendAdministratorErrorReport(db, source, summary, message):
    installed_sha1 = "<unknown>"
    sendAdministratorMessage(
        source,
        summary,
        """\

Critic encountered an unexpected error.  If you know a series of steps that can
reproduce this error it would be very useful if you submitted a bug report
including the steps plus the information below (see bug reporting URL at the
bottom of this e-mail).

%(message)s

Critic version: %(installed_sha1)s
Critic bug reports can be filed here: https://github.com/jensl/critic/issues/new
"""
        % {"message": message, "installed_sha1": installed_sha1},
    )


def sendExceptionMessage(db, source, exception):
    lines = exception.splitlines()
    sendAdministratorErrorReport(db, source, lines[-1], exception.rstrip())


def sendPendingMails(mails):
    from critic import background

    wakeup_service = False
    sent_mails = []

    for mail in mails:
        assert mail.filename.endswith(".txt.pending")
        sent_filename = mail.filename[: -len(".pending")]
        try:
            os.rename(mail.filename, sent_filename)
        except OSError:
            pass
        else:
            mail.filename = sent_filename
            sent_mails.append(mail)
            wakeup_service = True

    if wakeup_service:
        background.utils.wakeup_direct("maildelivery")

    return sent_mails


def cancelPendingMails(mails):
    for mail in mails:
        assert mail.filename.endswith(".txt.pending")
        try:
            os.unlink(mail.filename)
        except OSError:
            pass
