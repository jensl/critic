# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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

import base64
import email
import re
import socket
import threading

import testing


class MissingMail(testing.TestFailure):
    def __init__(self, criteria):
        super(MissingMail, self).__init__("No mail matching %r received" % criteria)
        self.criteria = criteria


class User(object):
    def __init__(self, name, address):
        self.name = name
        self.address = address


class Mail(object):
    def __init__(self, return_path):
        self.return_path = return_path
        self.recipient = None
        self.headers = {}
        self.lines = []

    @property
    def subject(self):
        return self.header("Subject", "<no subject>")

    def header(self, name, default=None):
        if name.lower() in self.headers:
            return self.headers[name.lower()][0]["value"]
        else:
            return default

    def all_headers(self):
        for header_name in sorted(self.headers.keys()):
            for header in self.headers[header_name]:
                yield (header["name"], header["value"])

    def __repr__(self):
        return "Mail(recipient=%r, subject=%r)" % (
            self.recipient,
            self.header("Subject"),
        )

    def __str__(self):
        return "%s\n\n%s" % (
            "\n".join(("%s: %s" % header) for header in self.all_headers()),
            "\n".join(self.lines),
        )


class EOF(Exception):
    pass


class Quit(Exception):
    pass


class Error(Exception):
    pass


class ParseError(Error):
    def __init__(self, line):
        super(ParseError, self).__init__("line=%r" % line)
        self.line = line


class Client(threading.Thread):
    def __init__(self, mailbox, client, debug_mails):
        super(Client, self).__init__()
        self.mailbox = mailbox
        self.credentials = mailbox.credentials
        self.client = client
        self.client.settimeout(None)
        self.debug_mails = debug_mails
        self.buffered = b""
        self.start()

    def sendline(self, string):
        self.client.sendall(("%s\r\n" % string).encode())

    def recvline(self):
        while b"\r\n" not in self.buffered:
            data = self.client.recv(4096)
            if not data:
                raise EOF
            self.buffered += data
        line, self.buffered = self.buffered.split(b"\r\n", 1)
        return line.decode()

    def expectline(self, pattern):
        line = self.recvline()
        match = re.match(pattern, line, re.IGNORECASE)
        if not match:
            raise ParseError(line)
        return match.groups()

    def handshake(self):
        self.sendline("220 critic.example.org I'm the Critic Testing Framework")

        line = self.recvline()
        if re.match(r"helo\s+(\S+)$", line, re.IGNORECASE):
            if self.credentials:
                raise Error
            self.sendline("250 critic.example.org")
        elif re.match(r"ehlo\s+(\S+)$", line, re.IGNORECASE):
            if self.credentials:
                self.sendline("250-critic.example.org")
                self.sendline("250 AUTH LOGIN")

                line = self.recvline()
                match = re.match(r"auth\s+login(?:\s+(.+))?$", line, re.IGNORECASE)
                if not match:
                    raise ParseError(line)

                (username_b64,) = match.groups()

                if not username_b64:
                    self.sendline(
                        "334 %s" % str(base64.b64encode(b"Username:"), encoding="ascii")
                    )
                    username_b64 = self.recvline()

                self.sendline(
                    "334 %s" % str(base64.b64encode(b"Password:"), encoding="ascii")
                )
                password_b64 = self.recvline()

                try:
                    username = str(base64.b64decode(username_b64), encoding="ascii")
                except TypeError:
                    raise Error("Invalid base64: %r" % username_b64)

                try:
                    password = str(base64.b64decode(password_b64), encoding="ascii")
                except TypeError:
                    raise Error("Invalid base64: %r" % password_b64)

                if (
                    username != self.credentials["username"]
                    or password != self.credentials["password"]
                ):
                    raise Error("Wrong credentials: %r / %r" % (username, password))

                self.sendline("235 Welcome, %s!" % username)

                testing.logger.debug("Mailbox: Client authenticated.")
            else:
                self.sendline("250 critic.example.org")
        else:
            raise Error

    def receive(self):
        try:
            (return_path,) = self.expectline(r"mail\s+from:<([^>]+)>(?:\s+size=\d+)?$")
        except ParseError as error:
            if error.line.lower() == "quit":
                self.sendline("221 critic.example.org Bye, bye")
                raise Quit
            raise

        self.sendline("250 OK")

        mail = Mail(return_path)

        # For simplicity we only support a single recipient.  Critic (currently)
        # never sends mails with multiple recipients.  (It often sends identical
        # mails to multiple recipients, but on the SMTP level, they are multiple
        # single-recipient mails.)
        (mail.recipient,) = self.expectline(r"rcpt\s+to:<([^>]+)>$")

        testing.logger.debug("Mailbox: Mail to <%s>." % mail.recipient)

        self.sendline("250 OK")
        self.expectline("data")
        self.sendline("354 Right")

        message_source = ""

        while True:
            line = self.recvline()
            if line == ".":
                break
            message_source += line + "\r\n"

        message = email.message_from_string(message_source)

        for name in message.keys():
            headers = mail.headers.setdefault(name.lower(), [])
            for value in message.get_all(name):
                value = re.sub("\r\n[ \t]+", " ", value)
                headers.append({"name": name, "value": value})

        mail.lines = message.get_payload(decode=True).decode().splitlines()

        testing.logger.debug(
            'Received mail to: <%s> "%s"' % (mail.recipient, mail.header("Subject"))
        )

        if self.debug_mails:
            source = "--------------------------------------------------\n"
            for name, value in message.items():
                source += "%s: %s\n" % (name, value)
            source += "\n"
            for line in mail.lines:
                source += line + "\n"
            source += "--------------------------------------------------"
            testing.logger.debug(source)

        self.mailbox.add(mail)
        self.sendline("250 OK")

    def run(self):
        try:
            testing.logger.debug("Mailbox: Client connected.")
            self.handshake()
            testing.logger.debug("Mailbox: Client ready.")
            while True:
                self.receive()
        except Error as error:
            testing.logger.error("Mailbox: Client error: %s" % error)
        except Quit:
            testing.logger.debug("Mailbox: Client quit.")
        except EOF:
            testing.logger.debug("Mailbox: Client disconnected prematurely.")
        except Exception:
            testing.logger.exception("Mailbox: Client error!")
        self.close()

    def close(self):
        try:
            self.client.close()
        except socket.error:
            pass


class Listener(threading.Thread):
    def __init__(self, mailbox, debug_mails):
        super(Listener, self).__init__()
        self.daemon = True
        self.mailbox = mailbox
        self.debug_mails = debug_mails
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(0.1)
        self.socket.bind(("", 0))
        self.socket.listen(1)
        self.stopped = False
        self.start()

    def run(self):
        while not self.stopped:
            try:
                client, _ = self.socket.accept()
            except socket.timeout:
                pass
            else:
                Client(self.mailbox, client, self.debug_mails)

    def stop(self):
        self.stopped = True


class Mailbox(object):
    def __init__(self, instance, credentials=None, debug_mails=False):
        self.instance = instance
        self.credentials = credentials
        self.queued = []
        self.errors = []
        self.condition = threading.Condition()
        self.listener = Listener(self, debug_mails)

    def add(self, mail):
        with self.condition:
            self.queued.append(mail)
            self.condition.notify()

    def pop(self, accept=None):
        def is_accepted(mail):
            if accept is None:
                return True
            if callable(accept):
                return accept(mail)
            for fn in accept:
                if not fn(mail):
                    return False
            return True

        def find_mail():
            with self.condition:
                for mail in self.queued:
                    if is_accepted(mail):
                        self.queued.remove(mail)
                        return mail

        mail = find_mail()
        if mail:
            return mail

        if accept is not None and self.instance:
            # Wait until the instance's mail delivery service is idle, which
            # means it has delivered all pending mail.  After that, the mail
            # should be here, or it never will be.
            self.instance.synchronize_service("maildelivery")

            mail = find_mail()
            if mail:
                return mail

        raise MissingMail(accept)

    def reset(self):
        with self.condition:
            self.queued = []

    def pop_error(self):
        with self.condition:
            return self.errors.pop(0)

    def stop(self):
        self.listener.stop()

    def check_empty(self):
        if self.instance:
            self.instance.synchronize_service("maildelivery")
        try:
            while True:
                unexpected = self.pop()
                testing.logger.error(
                    "Unexpected mail to <%s>:\n%s" % (unexpected.recipient, unexpected)
                )
        except MissingMail:
            pass

    @property
    def port(self):
        return self.listener.socket.getsockname()[1]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()
        return False


class WithSubject(object):
    def __init__(self, value):
        self.regexp = re.compile(value)

    def __call__(self, mail):
        return self.regexp.match(mail.header("Subject")) is not None

    def __repr__(self):
        return "subject=%r" % self.regexp.pattern


class ToRecipient(object):
    def __init__(self, address):
        self.address = address

    def __call__(self, mail):
        return mail.recipient == self.address

    def __repr__(self):
        return "recipient=<%s>" % self.address


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--quiet", action="store_true")

    credentials_group = parser.add_argument_group("Credentials")
    credentials_group.add_argument("--username")
    credentials_group.add_argument("--password")

    arguments = parser.parse_args()

    testing.configureLogging(arguments=arguments)

    if arguments.username and arguments.password:
        credentials = {"username": arguments.username, "password": arguments.password}
    else:
        credentials = None

    mailbox = Mailbox(None, credentials=credentials, debug_mails=arguments.debug)

    testing.logger.info("Listening at port %d", mailbox.port)

    with mailbox:
        while testing.pause("Press ctrl-c to exit.") != "stop":
            pass
