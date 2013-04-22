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

import socket
import threading
import time
import re
import base64
import logging

logger = logging.getLogger("critic")

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

    def header(self, name, default=None):
        if name.lower() in self.headers:
            return self.headers[name.lower()][0]["value"]
        else:
            return default

    def all_headers(self):
        for header_name in sorted(self.headers.keys()):
            for header in self.headers[header_name]:
                yield (header["name"], header["value"])

    def decode(self):
        if self.header("Content-Transfer-Encoding") == "base64":
            decoded = base64.b64decode("".join(self.lines))
            self.lines = decoded.splitlines()

    def __str__(self):
        return "%s\n\n%s" % ("\n".join(("%s: %s" % header)
                                       for header in self.all_headers()),
                             "\n".join(self.lines))

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
    def __init__(self, mailbox, client):
        super(Client, self).__init__()
        self.mailbox = mailbox
        self.client = client
        self.buffered = ""
        self.start()

    def sendline(self, string):
        self.client.sendall("%s\r\n" % string)

    def recvline(self):
        while "\r\n" not in self.buffered:
            data = self.client.recv(4096)
            if not data:
                raise EOF
            self.buffered += data
        line, self.buffered = self.buffered.split("\r\n", 1)
        return line

    def expectline(self, pattern):
        line = self.recvline()
        match = re.match(pattern, line, re.IGNORECASE)
        if not match:
            raise ParseError(line)
        return match.groups()

    def handshake(self):
        self.sendline("220 critic.example.org I'm the Critic Testing Framework")

        line = self.recvline()
        if not re.match(r"helo\s+(\S+)$", line, re.IGNORECASE) \
                and not re.match(r"ehlo\s+(\S+)$", line, re.IGNORECASE):
            raise Error

        self.sendline("250 critic.example.org")

    def receive(self):
        try:
            (return_path,) = self.expectline(r"mail\s+from:<([^>]+)>(?:\s+size=\d+)?$")
        except ParseError as error:
            if error.line.lower() == "quit":
                raise Quit
            raise

        self.sendline("250 OK")

        mail = Mail(return_path)

        # For simplicity we only support a single recipient.  Critic (currently)
        # never sends mails with multiple recipients.  (It often sends identical
        # mails to multiple recipients, but on the SMTP level, they are multiple
        # single-recipient mails.)
        (mail.recipient,) = self.expectline(r"rcpt\s+to:<([^>]+)>$")

        self.sendline("250 OK")
        self.expectline("data")
        self.sendline("354 Right")

        headers = True
        header = None

        while True:
            line = self.recvline()
            if line == ".":
                break
            if headers:
                if not line:
                    headers = False
                else:
                    if header and re.match(r"^\s+", line):
                        header["value"] = "%s %s" % (header["value"], line.strip())
                    else:
                        name, value = re.match(r"([^:]+):(.*)$", line).groups()
                        header = { "name": name.strip(),
                                   "value": value.strip() }
                        mail.headers.setdefault(name.strip().lower(), []).append(header)
            else:
                mail.lines.append(line)

        mail.decode()

        self.mailbox.add(mail)
        self.sendline("250 OK")

    def run(self):
        try:
            self.handshake()
            while True:
                self.receive()
        except Error as error:
            self.mailbox.add_error(error)
            self.client.close()
        except (EOF, Quit):
            pass

class Listener(threading.Thread):
    def __init__(self, mailbox):
        super(Listener, self).__init__()
        self.daemon = True
        self.mailbox = mailbox
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
                Client(self.mailbox, client)

    def stop(self):
        self.stopped = True

class Mailbox(object):
    def __init__(self):
        self.queued = []
        self.errors = []
        self.condition = threading.Condition()
        self.listener = Listener(self)

    def add(self, mail):
        with self.condition:
            self.queued.append(mail)
            self.condition.notify()

    def pop(self, accept=None, timeout=0):
        deadline = time.time() + timeout
        with self.condition:
            while True:
                for mail in self.queued:
                    if not accept or accept(mail):
                        self.queued.remove(mail)
                        return mail
                use_timeout = deadline - time.time()
                if use_timeout > 0:
                    self.condition.wait(use_timeout)
                else:
                    break
        return None

    def reset(self):
        with self.condition:
            self.queued = []

    def add_error(self, error):
        with self.condition:
            self.errors.append(error)

    def pop_error(self):
        with self.condition:
            return self.errors.pop(0)

    def stop(self):
        self.listener.stop()

    def check_empty(self):
        while True:
            unexpected = self.pop(timeout=1)
            if unexpected is None:
                return
            logger.error("Unexpected mail to <%s>:\n%s"
                         % (unexpected.recipient, unexpected))

    @property
    def port(self):
        return self.listener.socket.getsockname()[1]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()
        return False

def with_subject(value):
    regexp = re.compile(value)
    def accept(mail):
        return regexp.match(mail.header("Subject")) is not None
    return accept

def to_recipient(address):
    def accept(mail):
        return mail.recipient == address
    return accept
