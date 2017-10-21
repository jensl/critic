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

import os
import fcntl
import select
import cStringIO
import time
import errno

class ProcessTimeout(Exception):
    def __init__(self, timeout):
        super(ProcessTimeout, self).__init__(
            "Process timed out (after %d seconds)" % timeout)
        self.timeout = timeout

class ProcessError(Exception):
    def __init__(self, process, stderr):
        super(ProcessError, self).__init__(
            "Process returned non-zero exit status %d" % process.returncode)
        self.returncode = process.returncode
        self.stderr = stderr

def setnonblocking(fd):
    fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

class Communicate(object):
    def __init__(self, process):
        self.process = process
        self.timeout = None
        self.deadline = None
        self.stdin_data = None
        self.stdout_callbacks = [None, None]
        self.stderr_callbacks = [None, None]
        self.returncode = None

    def setTimeout(self, timeout):
        self.timeout = timeout
        self.deadline = time.time() + timeout

    def setInput(self, data):
        self.stdin_data = data

    def setCallbacks(self, stdout=None, stdout_line=None, stderr=None, stderr_line=None):
        assert stdout is None or stdout_line is None
        assert stderr is None or stderr_line is None
        self.stdout_callbacks[:] = stdout, stdout_line
        self.stderr_callbacks[:] = stderr, stderr_line

    def __read(self, source, target, callbacks):
        while True:
            cb_data, cb_line = callbacks
            try:
                if cb_line:
                    line = source.readline()
                    if not line:
                        return True
                    cb_line(line)
                else:
                    data = source.read()
                    if not data:
                        return True
                    if cb_data:
                        cb_data(data)
                    else:
                        target.write(data)
            except IOError as error:
                if error.errno == errno.EAGAIN:
                    return False
                raise

    def run(self):
        process = self.process
        poll = select.poll()

        if callable(self.stdin_data):
            stdin_data = ""
        else:
            stdin_data = self.stdin_data
            self.stdin_data = None
        stdin_done = False

        stdout = cStringIO.StringIO()
        stdout_done = False

        stderr = cStringIO.StringIO()
        stderr_done = False

        if process.stdin:
            setnonblocking(process.stdin)
            poll.register(process.stdin, select.POLLOUT)
        else:
            stdin_done = True

        if process.stdout:
            setnonblocking(process.stdout)
            poll.register(process.stdout, select.POLLIN)
        else:
            stdout_done = True

        if process.stderr:
            setnonblocking(process.stderr)
            poll.register(process.stderr, select.POLLIN)
        else:
            stderr_done = True

        while (not stdin_done or not stdout_done or not stderr_done) \
                and (self.deadline is None or time.time() < self.deadline):
            if self.deadline is None:
                timeout = None
            else:
                timeout = 1000 * (self.deadline - time.time())

            while True:
                try:
                    events = poll.poll(timeout)
                except select.error as error:
                    if error.errno == errno.EINTR:
                        continue
                    raise
                else:
                    break

            for fd, event in events:
                if not stdin_done and fd == process.stdin.fileno():
                    if callable(self.stdin_data):
                        data = self.stdin_data()
                        if data is None:
                            self.stdin_data = None
                        else:
                            stdin_data += data

                    if stdin_data:
                        nwritten = os.write(process.stdin.fileno(), stdin_data)
                        stdin_data = stdin_data[nwritten:]

                    if not stdin_data and self.stdin_data is None:
                        process.stdin.close()
                        stdin_done = True
                        poll.unregister(fd)

                if not stdout_done and fd == process.stdout.fileno():
                    stdout_done = self.__read(process.stdout, stdout,
                                              self.stdout_callbacks)
                    if stdout_done:
                        poll.unregister(fd)

                if not stderr_done and fd == process.stderr.fileno():
                    stderr_done = self.__read(process.stderr, stderr,
                                              self.stderr_callbacks)
                    if stderr_done:
                        poll.unregister(fd)

        if stdin_done and stdout_done and stderr_done:
            process.wait()

            stdout_data = stdout.getvalue() if process.stdout else None
            stderr_data = stderr.getvalue() if process.stderr else None

            self.returncode = process.returncode

            if self.returncode == 0:
                return stdout_data, stderr_data
            else:
                raise ProcessError(process, stderr_data)

        process.kill()
        process.wait()

        raise ProcessTimeout(self.timeout)
