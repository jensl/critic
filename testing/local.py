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
import sys

import testing

class Instance(testing.Instance):
    flags_on = ["local"]

    def has_flag(self, flag):
        return testing.has_flag("HEAD", flag)

    def unittest(self, module, tests, args=None):
        testing.logger.info("Running unit tests: %s (%s)"
                             % (module, ",".join(tests)))
        path = self.translateUnittestPath(module)
        if not args:
            args = []
        for test in tests:
            try:
                self.executeProcess([sys.executable, path, test] + args,
                                    cwd="src", log_stderr=False)
            except testing.CommandError as error:
                output = "\n  ".join(error.stderr.splitlines())
                testing.logger.error("Unit tests failed: %s: %s\nOutput:\n  %s"
                                     % (module, test, output))

    def filter_service_logs(self, level, service_names):
        # We have no services.
        pass
