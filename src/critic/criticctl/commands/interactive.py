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

import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)

from critic import api

name = "interactive"
title = "Interactive session"


def setup(parser):
    parser.add_argument("--user", "-u", help="Impersonate this user")
    parser.add_argument(
        "--install-ipython",
        action="store_true",
        help="Install IPython in the current virtual environment, using pip.",
    )


async def main(critic, arguments, *, recursive=False):
    try:
        import IPython
    except ImportError:
        if arguments.install_ipython and not recursive:
            subprocess.check_call(
                [os.path.join(sys.prefix, "bin", "pip"), "install", "IPython"]
            )
            return main(critic, arguments, recursive=True)

        logger.error("Failed to import IPython!")
        logger.info(
            "Rerun with --install-ipython to install it in the current "
            "virtual environment."
        )
        return 1

    if arguments.user:
        async with api.critic.startSession(for_user=True) as critic:
            await critic.setActualUser(await api.user.fetch(critic, arguments.user))

            IPython.embed()
    else:
        IPython.start_ipython(argv=[], user_ns={"api": api, "critic": critic})
