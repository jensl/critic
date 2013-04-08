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

class ProcessTimeout(Exception):
    pass

class ProcessError(Exception):
    def __init__(self, process, stderr):
        self.returncode = process.returncode
        self.stderr = stderr

def setnonblocking(fd):
    fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

def communicate(process, stdin_data, timeout):
    deadline = time.time() + timeout
    poll = select.poll()

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

    while (not stdin_done or not stdout_done or not stderr_done) and time.time() < deadline:
        for fd, event in poll.poll(1000 * (deadline - time.time())):
            if not stdin_done and fd == process.stdin.fileno():
                nwritten = os.write(process.stdin.fileno(), stdin_data)
                stdin_data = stdin_data[nwritten:]
                if not stdin_data:
                    process.stdin.close()
                    stdin_done = True
                    poll.unregister(fd)
            if not stdout_done and fd == process.stdout.fileno():
                data = process.stdout.read()
                if data:
                    stdout.write(data)
                else:
                    stdout_done = True
                    poll.unregister(fd)
            if not stderr_done and fd == process.stderr.fileno():
                data = process.stderr.read()
                if data:
                    stderr.write(data)
                else:
                    stderr_done = True
                    poll.unregister(fd)

    if stdin_done and stdout_done and stderr_done:
        process.wait()

        stdout_data = stdout.getvalue() if process.stdout else None
        stderr_data = stderr.getvalue() if process.stderr else None

        if process.returncode == 0:
            return stdout_data, stderr_data
        else:
            raise ProcessError(process, stderr_data)

    process.kill()
    process.wait()

    raise ProcessTimeout
