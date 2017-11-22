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

    def run_unittest(self, args):
        PYTHONPATH = os.path.join(os.getcwd())
        argv = [sys.executable, "-u", "-m", "critic.base.run_unittest"] + args
        return self.executeProcess(
            argv, cwd="src", log_stderr=False, env={"PYTHONPATH": PYTHONPATH}
        )

    def filter_service_logs(self, level, service_names):
        # We have no services.
        pass


def setup(subparsers):
    parser = subparsers.add_parser(
        "local",
        description="Local tests only.",
        help=(
            "Local testing means testing without actually installing Critic "
            "first. This is very quick, but can only run a limited set of "
            "unit tests."
        ),
    )
    parser.set_defaults(flavor="local")
