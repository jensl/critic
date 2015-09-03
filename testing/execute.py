# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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
import subprocess
import fcntl
import select
import errno

import testing

def setnonblocking(fd):
    fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

def execute(argv, timeout=None, interactive=False, log_stdout=True,
            log_stderr=True, mix_stdout_and_stderr=False, **kwargs):
    if interactive:
        process = subprocess.Popen(
            argv,
            **kwargs)

        stdout_data = ""
        stderr_data = ""
    else:
        process = subprocess.Popen(
            argv,
            stdin=open("/dev/null"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **kwargs)

        class BufferedLineReader(object):
            def __init__(self, source):
                self.source = source
                self.buffer = ""

            def readline(self):
                try:
                    while self.source is not None:
                        try:
                            line, self.buffer = self.buffer.split("\n", 1)
                        except ValueError:
                            pass
                        else:
                            return line + "\n"
                        data = self.source.read(1024)
                        if not data:
                            self.source = None
                            break
                        self.buffer += data
                    line = self.buffer
                    self.buffer = ""
                    return line
                except IOError as error:
                    if error.errno == errno.EAGAIN:
                        return None
                    raise

        stdout_data = ""
        stdout_reader = BufferedLineReader(process.stdout)

        stderr_data = ""
        stderr_reader = BufferedLineReader(process.stderr)

        setnonblocking(process.stdout)
        setnonblocking(process.stderr)

        poll = select.poll()
        poll.register(process.stdout)
        poll.register(process.stderr)

        stdout_done = False
        stderr_done = False

        while not (stdout_done and stderr_done):
            poll.poll()

            while not stdout_done:
                line = stdout_reader.readline()
                if line is None:
                    break
                elif not line:
                    poll.unregister(process.stdout)
                    stdout_done = True
                    break
                else:
                    stdout_data += line
                    if log_stdout:
                        testing.logger.log(testing.STDOUT, line.rstrip("\n"))

            while not stderr_done:
                line = stderr_reader.readline()
                if line is None:
                    break
                elif not line:
                    poll.unregister(process.stderr)
                    stderr_done = True
                    break
                else:
                    if mix_stdout_and_stderr:
                        stdout_data += line
                    else:
                        stderr_data += line
                    if log_stderr:
                        testing.logger.log(testing.STDERR, line.rstrip("\n"))

    process.wait()

    if process.returncode != 0:
        raise testing.CommandError(argv, stdout_data, stderr_data)

    return stdout_data
