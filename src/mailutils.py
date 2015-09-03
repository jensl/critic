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

import time
import os
import signal
import email.utils

import configuration
import dbutils

def generateMessageId(index=1):
    now = time.time()

    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime(now))
    timestamp_ms = "%04d" % ((now * 10000) % 10000)

    return "%s.%s.%04d" % (timestamp, timestamp_ms, index)

def queueMail(from_user, to_user, recipients, subject, body, message_id=None,
              parent_message_id=None, headers=None):
    if not message_id:
        message_id = generateMessageId()

    if headers is None:
        headers = {}
    else:
        headers = headers.copy()

    if parent_message_id:
        parent_message_id = "<%s@%s>" % (parent_message_id, configuration.base.HOSTNAME)

    filename = "%s/%s_%s_%s.txt.pending" % (configuration.paths.OUTBOX,
                                            from_user.name, to_user.name,
                                            message_id)

    with open(filename, "w") as file:
        print >> file, repr({ "message_id": message_id,
                              "parent_message_id": parent_message_id,
                              "headers": headers,
                              "time": time.time(),
                              "from_user": from_user,
                              "to_user": to_user,
                              "recipients": recipients,
                              "subject": subject,
                              "body": body })

    return filename

class User:
    def __init__(self, *args):
        if len(args) == 1:
            self.name = configuration.base.SYSTEM_USER_NAME
            self.fullname, self.email = email.utils.parseaddr(args[0])
        else:
            self.name, self.email, self.fullname = args

    def __repr__(self):
        return "User(%r, %r)" % (self.email, self.fullname)

def sendMessage(recipients, subject, body):
    from_user = User(configuration.base.SYSTEM_USER_NAME, configuration.base.SYSTEM_USER_EMAIL, "Critic System")
    filenames = []

    for to_user in recipients:
        filenames.append(queueMail(from_user, to_user, recipients, subject, body))

    sendPendingMails(filenames)

def sendAdministratorMessage(source, summary, message):
    recipients = []

    for recipient in configuration.base.SYSTEM_RECIPIENTS:
        recipients.append(User(recipient))

    sendMessage(recipients, "%s: %s" % (source, summary), message)

def sendAdministratorErrorReport(db, source, summary, message):
    if db:
        installed_sha1 = dbutils.getInstalledSHA1(db)
    else:
        installed_sha1 = "<unknown>"
    sendAdministratorMessage(source, summary, """\

Critic encountered an unexpected error.  If you know a series of steps that can
reproduce this error it would be very useful if you submitted a bug report
including the steps plus the information below (see bug reporting URL at the
bottom of this e-mail).

%(message)s

Critic version: %(installed_sha1)s
Critic bug reports can be filed here: https://github.com/jensl/critic/issues/new
""" % { "message": message, "installed_sha1": installed_sha1 })

def sendExceptionMessage(db, source, exception):
    lines = exception.splitlines()
    sendAdministratorErrorReport(db, source, lines[-1], exception.rstrip())

def sendPendingMails(filenames):
    for filename in filenames:
        assert filename.endswith(".txt.pending")
        try:
            os.rename(filename, filename[:-len(".pending")])
        except OSError:
            pass

    try:
        pid = int(open(configuration.services.MAILDELIVERY["pidfile_path"]).read().strip())
        os.kill(pid, signal.SIGHUP)
    except:
        pass

def cancelPendingMails(filenames):
    for filename in filenames:
        assert filename.endswith(".txt.pending")
        try:
            os.unlink(filename)
        except OSError:
            pass
