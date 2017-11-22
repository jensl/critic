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


def execute(
    argv,
    timeout=None,
    interactive=False,
    log_stdout=True,
    log_stderr=True,
    mix_stdout_and_stderr=False,
    stdin_data=None,
    pid_callback=None,
    **kwargs
):
    if interactive:
        process = subprocess.Popen(argv, **kwargs)

        stdout_data = ""
        stderr_data = ""
    else:
        if stdin_data is None:
            stdin_mode = subprocess.DEVNULL
        else:
            stdin_mode = subprocess.PIPE
            stdin_data = stdin_data.encode()

        process = subprocess.Popen(
            argv,
            stdin=stdin_mode,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            **kwargs
        )

        if pid_callback:
            pid_callback(process.pid)

        class BufferedLineReader(object):
            def __init__(self, source):
                self.source = source
                self.buffer = b""

            def readline(self):
                try:
                    while self.source is not None:
                        try:
                            line, self.buffer = self.buffer.split(b"\n", 1)
                        except ValueError:
                            pass
                        else:
                            return line.decode() + "\n"
                        data = self.source.read()
                        if data is None:
                            return None
                        if not data:
                            self.source = None
                            break
                        self.buffer += data
                    line = self.buffer
                    self.buffer = b""
                    return line.decode()
                except IOError as error:
                    if error.errno == errno.EAGAIN:
                        return None
                    raise

        stdout_data = ""
        stdout_reader = BufferedLineReader(process.stdout)

        stderr_data = ""
        stderr_reader = BufferedLineReader(process.stderr)

        if process.stdin:
            setnonblocking(process.stdin)
        setnonblocking(process.stdout)
        setnonblocking(process.stderr)

        poll = select.poll()
        if stdin_data:
            poll.register(process.stdin)
        poll.register(process.stdout)
        poll.register(process.stderr)

        stdout_done = False
        stderr_done = False

        while stdin_data or not (stdout_done and stderr_done):
            poll.poll()

            try:
                while stdin_data:
                    written = process.stdin.write(stdin_data)
                    stdin_data = stdin_data[written:]
                    if not stdin_data:
                        poll.unregister(process.stdin)
                        process.stdin.close()
            except BlockingIOError:
                pass

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
                        line = line.rstrip("\n").rstrip("\r")
                        if callable(log_stdout):
                            log_stdout(line)
                        else:
                            testing.logger.log(testing.STDOUT, line)

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
                        line = line.rstrip("\n").rstrip("\r")
                        if callable(log_stderr):
                            log_stderr(line)
                        else:
                            testing.logger.log(testing.STDERR, line)

    process.wait()

    if process.returncode != 0:
        raise testing.CommandError(argv, stdout_data, stderr_data, process.returncode)

    return stdout_data
