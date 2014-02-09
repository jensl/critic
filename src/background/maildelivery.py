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
import json

import smtplib
import email.mime.text
import email.header
import email.utils

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import configuration
import background.utils

class User:
    def __init__(self, *args):
        if len(args) > 1:
            self.email, self.fullname = args[-2:]
        else:
            self.fullname, self.email = email.utils.parseaddr(args[0])

class MailDelivery(background.utils.PeerServer):
    def __init__(self, credentials):
        # We disable the automatic administrator mails (using the
        # 'send_administrator_mails' argument) since
        #
        # 1) it's pretty pointless to report mail delivery problems
        #    via mail, and
        #
        # 2) it can cause runaway mail generation, since failure to
        #    timely deliver the mail delivery problem report emails
        #    would trigger further automatic problem report emails.
        #
        # Instead, we keep track of having encountered any problems,
        # and send a single administrator mail ("check the logs")
        # after having successfully delivered an email.

        service = configuration.services.MAILDELIVERY

        super(MailDelivery, self).__init__(service=service,
                                           send_administrator_mails=False)

        self.__credentials = credentials
        self.__connection = None
        self.__connection_timeout = service.get("timeout")
        self.__has_logged_warning = 0
        self.__has_logged_error = 0

        self.register_maintenance(hour=3, minute=45, callback=self.__cleanup)

    def __sendAdministratorMessage(self):
        from_user = User(configuration.base.SYSTEM_USER_EMAIL, "Critic System")
        recipients = []

        for recipient in configuration.base.SYSTEM_RECIPIENTS:
            recipients.append(User(recipient))

        if self.__has_logged_warning and self.__has_logged_error:
            what = "%d warning%s and %d error%s" % (self.__has_logged_warning,
                                                    "s" if self.__has_logged_warning > 1 else "",
                                                    self.__has_logged_error,
                                                    "s" if self.__has_logged_error > 1 else "")
        elif self.__has_logged_warning:
            what = "%d warning%s" % (self.__has_logged_warning,
                                     "s" if self.__has_logged_warning > 1 else "")
        else:
            what = "%d error%s" % (self.__has_logged_error,
                                     "s" if self.__has_logged_error > 1 else "")

        for to_user in recipients:
            self.__send(message_id=None,
                        parent_message_id=None,
                        headers={},
                        from_user=from_user,
                        to_user=to_user,
                        recipients=recipients,
                        subject="maildelivery: check the logs!",
                        body="%s have been logged.\n\n-- critic\n" % what,
                        try_once=True)

        self.__has_logged_warning = 0
        self.__has_logged_error = 0

    def run(self):
        try:
            sleeptime = 0

            while not self.terminated:
                self.interrupted = False

                filenames = os.listdir(configuration.paths.OUTBOX)
                pending = []

                for filename in filenames:
                    if filename.endswith(".txt"):
                        pending.append("%s/%s" % (configuration.paths.OUTBOX, filename))

                if pending:
                    self.__connect()

                    # We may have been terminated while attempting to connect.
                    if self.terminated:
                        return

                    sleeptime = 0

                    now = time.time()

                    def age(filename):
                        return now - os.stat(filename).st_ctime

                    too_old = len(filter(lambda filename: age(filename) > 60, pending))
                    oldest_age = max(map(age, pending))

                    if too_old > 0:
                        self.warning(("%d files were created more than 60 seconds ago\n"
                                      "  The oldest is %s which is %d seconds old.")
                                     % (too_old, os.path.basename(filename), oldest_age))
                        self.__has_logged_warning += 1

                    for filename in sorted(pending):
                        lines = open(filename).readlines()

                        try:
                            if self.__send(**eval(lines[0])):
                                os.rename(filename, "%s/sent/%s.sent" % (configuration.paths.OUTBOX, os.path.basename(filename)))

                                if self.__has_logged_warning or self.__has_logged_error:
                                    try: self.__sendAdministratorMessage()
                                    except:
                                        self.exception()
                                        self.__has_logged_error += 1

                            # We may have been terminated while attempting to send.
                            if self.terminated:
                                return
                        except:
                            self.exception()
                            self.__has_logged_error += 1
                            os.rename(filename, "%s/%s.invalid" % (configuration.paths.OUTBOX, os.path.basename(filename)))
                            continue
                else:
                    if sleeptime > 25:
                        self.__disconnect()

                    before = time.time()
                    timeout = (30 - sleeptime) if self.__connection else self.run_maintenance()

                    self.debug("sleeping %d seconds" % timeout)

                    time.sleep(timeout)

                    if self.interrupted:
                        self.debug("sleep interrupted after %.2f seconds" % (time.time() - before))

                    sleeptime += (time.time() - before)
        finally:
            self.__disconnect()

    def __connect(self):
        if not self.__connection:
            attempts = 0

            while not self.terminated:
                attempts += 1

                try:
                    if configuration.smtp.USE_SSL:
                        self.__connection = smtplib.SMTP_SSL(timeout=self.__connection_timeout)
                    else:
                        self.__connection = smtplib.SMTP(timeout=self.__connection_timeout)

                    self.__connection.connect(configuration.smtp.HOST, configuration.smtp.PORT)

                    if configuration.smtp.USE_STARTTLS:
                        self.__connection.starttls()

                    if self.__credentials:
                        self.__connection.login(self.__credentials["username"],
                                                self.__credentials["password"])

                    self.debug("connected")
                    return
                except:
                    self.debug("failed to connect to SMTP server")
                    if (attempts % 5) == 0:
                        self.error("Failed to connect to SMTP server %d times.  "
                                   "Will keep retrying." % attempts)
                        self.__has_logged_error += 1
                    self.__connection = None

                seconds = min(60, 2 ** attempts)

                self.debug("sleeping %d seconds" % seconds)

                time.sleep(seconds)

    def __disconnect(self):
        if self.__connection:
            try:
                self.__connection.quit()
                self.debug("disconnected")
            except: pass

            self.__connection = None

    def __send(self, message_id, parent_message_id, headers, from_user, to_user, recipients, subject, body, **kwargs):
        def isascii(s):
            return all(ord(c) < 128 for c in s)

        def usersAsHeader(users, header_name):
            header = email.header.Header(header_name=header_name)

            for index, user in enumerate(users):
                if isascii(user.fullname):
                    header.append(user.fullname, "us-ascii")
                else:
                    header.append(user.fullname, "utf-8")
                if index < len(users) - 1:
                    header.append("<%s>," % user.email, "us-ascii")
                else:
                    header.append("<%s>" % user.email, "us-ascii")

            return header

        def stringAsHeader(s, name):
            if isascii(s): return email.header.Header(s, "us-ascii", header_name=name)
            else: return email.header.Header(s, "utf-8", header_name=name)

        message = email.mime.text.MIMEText(body, "plain", "utf-8")
        recipients = filter(lambda user: bool(user.email), recipients)

        if not to_user.email:
            return True

        if message_id:
            message_id = "<%s@%s>" % (message_id, configuration.base.HOSTNAME)
            message["Message-ID"] = message_id
        else:
            message_id = "N/A"

        if parent_message_id:
            message["In-Reply-To"] = parent_message_id
            message["References"] = parent_message_id

        message["From"] = usersAsHeader([from_user], "From")
        message["To"] = usersAsHeader(recipients, "To")
        message["Subject"] = stringAsHeader(subject, "Subject")

        for name, value in headers.items():
            message[name] = value

        self.debug("%s => %s (%s)" % (from_user.email, to_user.email, message_id))

        # Used from __sendAdministratorMessage(); we'll try once to send it even
        # if self.terminated.
        try_once = kwargs.get("try_once", False)

        attempts = 0

        while try_once or not self.terminated:
            try_once = False

            try:
                self.__connection.sendmail(configuration.base.SYSTEM_USER_EMAIL, [to_user.email], message.as_string())
                return True
            except:
                self.exception()
                self.__has_logged_error += 1

                if self.terminated:
                    return False

                attempts += 1
                sleeptime = min(60, 2 ** attempts)

                self.error("delivery failure: sleeping %d seconds" % sleeptime)

                self.__disconnect()
                time.sleep(sleeptime)
                self.__connect()

        # We were terminated before the mail was sent.  Return false to keep the
        # mail in the outbox for later delivery.
        return False

    def __cleanup(self):
        now = time.time()
        deleted = 0

        for filename in os.listdir(os.path.join(configuration.paths.OUTBOX, "sent")):
            if filename.endswith(".txt.sent"):
                filename = os.path.join(configuration.paths.OUTBOX, "sent", filename)
                age = now - os.stat(filename).st_ctime

                if age > 7 * 24 * 60 * 60:
                    os.unlink(filename)
                    deleted += 1

        if deleted:
            self.info("deleted %d files from %s"
                      % (deleted, os.path.join(configuration.paths.OUTBOX, "sent")))

def start_service():
    stdin_data = sys.stdin.read()

    if stdin_data:
        credentials = json.loads(stdin_data)["credentials"]
        if not credentials.get("username") or not credentials.get("password"):
            credentials = None
    else:
        credentials = None

    maildelivery = MailDelivery(credentials)
    maildelivery.run()

background.utils.call("maildelivery", start_service)
