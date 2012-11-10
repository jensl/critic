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

import smtplib
import email.mime.text
import email.header

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import configuration

from background.utils import PeerServer

class User():
    def __init__(self, id, name, email, fullname):
        self.id = id
        self.name = name
        self.email = email
        self.fullname = fullname

class MailDelivery(PeerServer):
    def __init__(self):
        super(MailDelivery, self).__init__(service=configuration.services.MAILDELIVERY)

        self.__connection = None

        self.register_maintenance(hour=3, minute=45, callback=self.__cleanup)

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
                    sleeptime = 0

                    for filename in sorted(pending):
                        age = time.time() - os.stat(filename).st_ctime

                        if age > 60:
                            self.warning("%s: file created %d seconds ago" % (os.path.basename(filename), age))

                        lines = open(filename).readlines()

                        try:
                            self.__send(**eval(lines[0]))
                        except:
                            self.exception()
                            os.rename(filename, "%s/%s.invalid" % (configuration.paths.OUTBOX, os.path.basename(filename)))
                            continue

                        os.rename(filename, "%s/sent/%s.sent" % (configuration.paths.OUTBOX, os.path.basename(filename)))
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

            while True:
                try:
                    if configuration.smtp.USE_SSL:
                        self.__connection = smtplib.SMTP_SSL()
                    else:
                        self.__connection = smtplib.SMTP()

                    self.__connection.connect(configuration.smtp.HOST, configuration.smtp.PORT)

                    if configuration.smtp.USE_STARTTLS:
                        self.__connection.starttls()

                    if configuration.smtp.USERNAME and configuration.smtp.PASSWORD:
                        self.__connection.login(configuration.smtp.USERNAME, configuration.smtp.PASSWORD)

                    self.debug("connected")
                    break
                except:
                    self.error("failed to connect to SMTP server")

                attempts += 1
                seconds = min(60, 2 ** attempts)

                self.info("sleeping %d seconds" % seconds)

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
            return

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

        attempts = 0

        while True:
            try:
                self.__connection.sendmail(configuration.base.SYSTEM_USER_EMAIL, [to_user.email], message.as_string())
                return
            except:
                self.exception()

                attempts += 1
                sleeptime = min(60, 2 ** attempts)

                self.error("delivery failure: sleeping %d seconds" % sleeptime)

                self.__disconnect()
                time.sleep(sleeptime)
                self.__connect()

    def __cleanup(self):
        now = time.time()
        deleted = 0

        for filename in os.listdir(os.path.join(configuration.paths.OUTBOX, "sent")):
            if filename.endswith(".txt"):
                filename = os.path.join(configuration.paths.OUTBOX, "sent", filename)
                age = now - os.stat(filename).st_ctime

                if age > 7 * 24 * 60 * 60:
                    os.unlink(filename)
                    deleted += 1

        if deleted: self.info("deleted %d files from %s" % (deleted, os.path.join(configuration.paths.OUTBOX, "sent")))

maildelivery = MailDelivery()
maildelivery.run()
