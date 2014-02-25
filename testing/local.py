# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 Jens Lindström, Opera Software ASA
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

import testing

class CommandError(Exception):
    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr

class Instance(testing.Instance):
    def execute(self, args, log_stdout=True, log_stderr=True, **kwargs):
        process = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        stdout, stderr = process.communicate()
        if stdout.strip() and log_stdout:
            testing.logger.log(testing.STDOUT, stdout.rstrip("\n"))
        if stderr.strip() and log_stderr:
            testing.logger.log(testing.STDERR, stderr.rstrip("\n"))
        if process.returncode != 0:
            raise CommandError(stdout, stderr)
        return stdout

    def unittest(self, module, tests, args=None):
        testing.logger.info("Running unit tests: %s (%s)"
                             % (module, ",".join(tests)))
        path = self.translateUnittestPath(module)
        if not args:
            args = []
        for test in tests:
            try:
                self.execute(["python", path, test] + args,
                             cwd="src", log_stderr=False)
            except CommandError as error:
                output = "\n  ".join(error.stderr.splitlines())
                testing.logger.error("Unit tests failed: %s: %s\nOutput:\n  %s"
                                     % (module, test, output))
