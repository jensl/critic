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

import configuration
import dbutils
import time
import os
import signal

def generateMessageId(index=1):
    now = time.time()

    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime(now))
    timestamp_ms = "%04d" % ((now * 10000) % 10000)

    return "%s.%s.%04d" % (timestamp, timestamp_ms, index)

def queueMail(from_user, to_user, recipients, subject, body, review_url=None, review_association=None, message_id=None, parent_message_id=None):
    if not message_id: message_id = generateMessageId()

    filename = "%s/%s_%s_%s.txt.pending" % (configuration.paths.OUTBOX, from_user.name, to_user.name, message_id)
    file = open(filename, "w")

    headers = {}
    if review_url:
        headers["OperaCritic-URL"] = review_url
    if review_association:
        headers["OperaCritic-Association"] = review_association

    print >> file, repr({ "message_id": message_id,
                          "parent_message_id": parent_message_id,
                          "headers": headers,
                          "from_user": from_user,
                          "to_user": to_user,
                          "recipients": recipients,
                          "subject": subject,
                          "body": body })

    file.close()
    return filename

class User:
    def __init__(self, name, email, fullname):
        self.name = name
        self.email = email
        self.fullname = fullname

    def __repr__(self):
        return "User(None, %r, %r, %r)" % (self.name, self.email, self.fullname)

def sendMessage(recipients, subject, body):
    from_user = User(configuration.base.SYSTEM_USER_NAME, configuration.base.SYSTEM_USER_EMAIL, "Critic System")
    filenames = []

    for to_user in recipients:
        filenames.append(queueMail(from_user, to_user, recipients, subject, body))

    sendPendingMails(filenames)

def sendAdministratorMessage(source, summary, message):
    recipients = []

    for administrator in configuration.base.ADMINISTRATORS:
        recipients.append(User(**administrator))

    sendMessage(recipients, "%s: %s" % (source, summary), message)

def sendExceptionMessage(source, exception):
    lines = exception.splitlines()
    sendAdministratorMessage(source, lines[-1], exception.rstrip() + "\n\n-- critic")

def sendPendingMails(filenames):
    for filename in filenames:
        if filename.endswith(".txt.pending"):
            os.rename(filename, filename[:-len(".pending")])

    try:
        pid = int(open(configuration.services.MAILDELIVERY["pidfile_path"]).read().strip())
        os.kill(pid, signal.SIGHUP)
    except:
        pass
