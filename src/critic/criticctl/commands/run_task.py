# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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
import logging
import sys

logger = logging.getLogger(__name__)

name = "run-task"
title = "Run task"
allow_missing_configuration = True


def setup(parser):
    # FIXME: This is a fairly ugly hack to speed up execution.
    if "run-task" not in sys.argv:
        return

    from .. import tasks

    configuration = parser.get_default("configuration")
    critic = parser.get_default("critic")

    parser.set_defaults(parser=parser)

    subparsers = parser.add_subparsers(metavar="TASK")

    for task_module in tasks.modules:
        if not configuration:
            if not getattr(task_module, "allow_missing_configuration", False):
                continue

        task_parser = subparsers.add_parser(
            task_module.name,
            description=task_module.description,
            help=task_module.description,
        )
        task_parser.set_defaults(
            configuration=configuration, critic=critic, task_module=task_module
        )
        task_module.setup(task_parser)


async def main(critic, arguments):
    from .. import tasks

    if not hasattr(arguments, "task_module"):
        arguments.parser.print_help()
        return 0

    try:
        result = arguments.task_module.main(critic, arguments)
        if asyncio.iscoroutine(result):
            result = await result
        return 0 if result is None else result
    except tasks.TaskFailed:
        return 1
