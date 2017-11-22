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

import argparse
import asyncio
import importlib
import logging
import os
import signal
import sys
import traceback
from typing import AsyncContextManager

logger = logging.getLogger(__name__)

from critic import api
from critic.background.extensionhost import CallError
from critic.base import asyncutils, binarylog

from . import write_message
from .endpoint import EndpointImpl
from .subscription import SubscriptionImpl


async def main_async() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-fd", type=int, required=True)
    parser.add_argument("--command-fd", type=int, required=True)
    parser.add_argument("--response-fd", type=int, required=True)
    # parser.add_argument("--extension-id", type=int, required=True)
    # parser.add_argument("--user-id", type=int)
    # parser.add_argument("--authentication-label", action="append", default=[])
    parser.add_argument(
        "--role-type", choices=("endpoint", "subscription"), required=True
    )
    parser.add_argument("--target", required=True)

    arguments = parser.parse_args()

    command_reader = await asyncutils.create_reader(arguments.command_fd)
    response_writer = await asyncutils.create_writer(arguments.response_fd)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(binarylog.BinaryHandler(os.fdopen(arguments.log_fd, "wb")))

    module_name, _, function_name = arguments.target.partition(":")

    logger.debug("running %s:%s", module_name, function_name)

    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        await write_message(
            response_writer, CallError("Could not import target module", str(error))
        )
        return 1

    try:
        function = getattr(module, function_name)
    except AttributeError as error:
        await write_message(
            response_writer, CallError("Could not find target function", str(error))
        )
        return 1

    async with api.critic.startSession(for_system=True) as critic:
        if arguments.role_type == "endpoint":
            runner = EndpointImpl(critic, command_reader, response_writer)
        elif arguments.role_type == "subscription":
            runner = SubscriptionImpl(critic, command_reader, response_writer)
        else:
            return 1

        try:
            await function(critic, runner)
        except Exception as error:
            details = str(error)
            stacktrace = traceback.format_exc()

            if not runner.handle_exception(details, stacktrace):
                await write_message(
                    response_writer,
                    CallError("Extension crashed", details, stacktrace),
                )
            return 1

    return 0


def main():
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    sys.exit(asyncio.run(main_async()))
