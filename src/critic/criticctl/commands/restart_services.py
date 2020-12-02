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
import logging

logger = logging.getLogger(__name__)

from critic import api

name = "restart-services"
title = "Restart Critic background services"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(need_session=True)


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
    # from critic import background

    # await background.utils.issue_command(
    #     critic,
    #     "servicemanager",
    #     {"command": "restart", "service": "servicemanager", "timeout": 10},
    # )

    return 0
