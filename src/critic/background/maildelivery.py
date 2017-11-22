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

import asyncio
import email.header
import email.mime.text
import email.utils
import errno
import json
import logging
import os
import smtplib
import time

logger = logging.getLogger("critic.background.maildelivery")

from critic import api
from critic import base
from critic import background
from critic import dbutils
from critic import mailutils


class MailDeliveryService(background.service.BackgroundService):
    name = "maildelivery"

    # We disable the automatic administrator mails since
    #
    # 1) it's pretty pointless to report mail delivery problems via mail, and
    #
    # 2) it can cause runaway mail generation, since failure to timely deliver
    #    the mail delivery problem report emails would trigger further automatic
    #    problem report emails.
    #
    # Instead, we keep track of having encountered any problems, and send a
    # single administrator mail ("check the logs") after having successfully
    # delivered an email.
    send_administrator_mails = False

    want_pubsub = True

    def __init__(self):
        super(MailDeliveryService, self).__init__()

        self.__connection = None
        self.__connection_timeout = self.service_settings.connection_timeout
        self.__has_logged_warning = 0
        self.__has_logged_error = 0

        self.__outbox_dir = os.path.join(base.configuration()["paths.home"], "outbox")

    def will_start(self):
        return self.settings.smtp.configured

    async def did_start(self):
        self.register_maintenance(self.__cleanup, "3:45")

    def __sendAdministratorMessage(self):
        def user(email, fullname):
            return {"email": email, "fullname": fullname}

        from_user = user(api.critic.getSystemEmail(), "Critic System")
        recipients = []

        for recipient in self.settings.system.recipients:
            recipients.append(user(recipient))

        if self.__has_logged_warning and self.__has_logged_error:
            what = "%d warning%s and %d error%s" % (
                self.__has_logged_warning,
                "s" if self.__has_logged_warning > 1 else "",
                self.__has_logged_error,
                "s" if self.__has_logged_error > 1 else "",
            )
        elif self.__has_logged_warning:
            what = "%d warning%s" % (
                self.__has_logged_warning,
                "s" if self.__has_logged_warning > 1 else "",
            )
        else:
            what = "%d error%s" % (
                self.__has_logged_error,
                "s" if self.__has_logged_error > 1 else "",
            )

        for to_user in recipients:
            self.__send(
                message_id=None,
                parent_message_id=None,
                headers={},
                date=time.time(),
                from_user=from_user,
                to_user=to_user,
                recipients=recipients,
                subject="maildelivery: check the logs!",
                body="%s have been logged.\n\n-- critic\n" % what,
                try_once=True,
            )

        self.__has_logged_warning = 0
        self.__has_logged_error = 0

    async def wake_up(self):
        logger.debug("woke up")

        sent_dir = os.path.join(self.__outbox_dir, "sent")

        try:
            os.makedirs(sent_dir)
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise

        pending = set()

        async with self.start_session() as critic:
            events = await api.systemevent.fetchAll(
                critic, category="maildelivery", pending=True
            )
            if events:
                async with api.transaction.start(critic) as transaction:
                    for event in events:
                        if event.key == "test-email":
                            sent_mails = mailutils.sendMessage(
                                event.data["to"],
                                event.data["subject"],
                                event.data["body"],
                            )
                            for sent_mail in sent_mails:
                                pending.add(sent_mail.filename)
                            transaction.modifySystemEvent(event).markAsHandled()

        for filename in os.listdir(self.__outbox_dir):
            if filename.endswith(".txt"):
                pending.add(os.path.join(self.__outbox_dir, filename))

        if pending:
            await self.__connect()
            await asyncio.sleep(0)

            now = time.time()

            def age(filename):
                return now - os.stat(filename).st_ctime

            too_old = sum(age(filename) > 60 for filename in pending)
            oldest_age = max(map(age, pending))

            if too_old > 0:
                logger.warning(
                    (
                        "%d files were created more than 60 seconds ago\n"
                        "  The oldest is %s which is %d seconds old."
                    ),
                    too_old,
                    os.path.basename(filename),
                    oldest_age,
                )
                self.__has_logged_warning += 1

            for filename in sorted(pending):
                with open(filename, "r", encoding="utf-8") as file:
                    data = json.load(file)

                try:
                    sent_mail = self.__send(**data)
                except Exception:
                    logger.exception("Failed to sent")
                    self.__has_logged_error += 1
                    os.rename(filename, filename + ".invalid")
                else:
                    if sent_mail:
                        os.rename(
                            filename,
                            os.path.join(
                                sent_dir, os.path.basename(filename) + ".sent"
                            ),
                        )

                        if self.__has_logged_warning or self.__has_logged_error:
                            try:
                                self.__sendAdministratorMessage()
                            except Exception:
                                logger.exception("Failed to send administrator message")
                                self.__has_logged_error += 1

                await asyncio.sleep(0)

            return self.service_settings.connection_idle_timeout
        else:
            self.__disconnect()

    async def pubsub_connected(self, client):
        def handle_message(channel, message):
            logger.debug("received message: %r", message)
            if message["scope"] != "systemevents" or message["action"] != "created":
                return
            event = message["event"]
            if event["category"] != "maildelivery":
                return
            if event["key"] == "test-email":
                self.do_wake_up()

        await self.pubsub.subscribe("systemevents", handle_message)

        # Wake us up once ASAP, in case something happened while we did not have
        # a connection to the Publish/Subscribe service.
        self.do_wake_up()

    async def will_stop(self):
        self.__disconnect()

    async def __connect(self):
        if self.__connection:
            return

        connection = None
        attempts = 0

        while True:
            try:
                if self.settings.smtp.use_smtps:
                    factory = smtplib.SMTP_SSL
                else:
                    factory = smtplib.SMTP

                connection = factory(timeout=self.__connection_timeout)

                logger.debug(
                    "connecting to %s:%d",
                    self.settings.smtp.address.host,
                    self.settings.smtp.address.port,
                )

                connection.connect(
                    self.settings.smtp.address.host, self.settings.smtp.address.port
                )

                logger.debug("connected")

                if self.settings.smtp.use_starttls:
                    connection.starttls()

                if self.settings.smtp.credentials.username is not None:
                    connection.login(
                        self.settings.smtp.credentials.username,
                        self.settings.smtp.credentials.password,
                    )

                break
            except Exception:
                attempts += 1

                logger.debug("failed to connect to SMTP server")

                if attempts == 5:
                    logger.error(
                        (
                            "Failed to connect to SMTP server %d times. "
                            "Will keep retrying."
                        ),
                        attempts,
                    )
                    self.__has_logged_error += 1

                self.__connection = None

            await asyncio.sleep(min(self.__connection_timeout, 2 ** attempts))

        logger.debug("connected")

        self.__connection = connection

    def __disconnect(self):
        if not self.__connection:
            return

        try:
            self.__connection.quit()
        except Exception:
            logger.exception("Closing connection crashed")
        else:
            logger.debug("disconnected")

        self.__connection = None

    def __send(
        self,
        message_id,
        parent_message_id,
        headers,
        from_user,
        to_user,
        recipients,
        subject,
        body,
        **kwargs
    ):
        def isascii(s):
            return all(ord(c) < 128 for c in s)

        def usersAsHeader(users, header_name):
            header = email.header.Header(header_name=header_name)

            for index, user in enumerate(users):
                if isascii(user["fullname"]):
                    header.append(user["fullname"], "us-ascii")
                else:
                    header.append(user["fullname"], "utf-8")
                if index < len(users) - 1:
                    header.append("<%s>," % user["email"], "us-ascii")
                else:
                    header.append("<%s>" % user["email"], "us-ascii")

            return header

        def stringAsHeader(s, name):
            if isascii(s):
                return email.header.Header(s, "us-ascii", header_name=name)
            else:
                return email.header.Header(s, "utf-8", header_name=name)

        message = email.mime.text.MIMEText(body, "plain", "utf-8")
        recipients = [user for user in recipients if user["email"]]

        if not to_user["email"]:
            return True

        if message_id:
            message_id = "<%s@%s>" % (message_id, self.settings.system.hostname)
            message["Message-ID"] = message_id
        else:
            message_id = "N/A"

        if parent_message_id:
            message["In-Reply-To"] = parent_message_id
            message["References"] = parent_message_id

        message["From"] = usersAsHeader([from_user], "From")
        message["To"] = usersAsHeader(recipients, "To")
        message["Subject"] = stringAsHeader(subject, "Subject")
        message["Date"] = email.utils.formatdate(kwargs.get("date", time.time()))

        for name, value in headers.items():
            message[name] = value

        logger.debug("%s => %s (%s)", from_user["email"], to_user["email"], message_id)

        try:
            self.__connection.sendmail(
                api.critic.getSystemEmail(), [to_user["email"]], message.as_string()
            )
        except Exception:
            logger.exception("Failed to send mail")
            return False
        else:
            return True

    async def __cleanup(self):
        now = time.time()
        deleted = 0

        sent_dir = os.path.join(self.__outbox_dir, "sent")

        for filename in os.listdir(sent_dir):
            if filename.endswith(".txt.sent"):
                filename = os.path.join(sent_dir, filename)
                age = now - os.stat(filename).st_ctime

                if age > 7 * 24 * 60 * 60:
                    os.unlink(filename)
                    deleted += 1

        if deleted:
            logger.info("deleted %d files from %s", deleted, sent_dir)


if __name__ == "__main__":
    background.service.call(MailDeliveryService)
