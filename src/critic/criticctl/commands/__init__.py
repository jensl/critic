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
from typing import Protocol, Sequence, cast

from critic import api
from . import addextension
from . import addrepository
from . import addrole
from . import adduser
from . import configuration
from . import connect
from . import delrole
from . import deluser
from . import disconnect
from . import interactive
from . import listusers
from . import lookup_ssh_key
from . import passwd
from . import run_extensionhost
from . import run_frontend
from . import run_services
from . import run_sshd
from . import run_task
from . import run_worker
from . import send_email
from . import settings
from . import sshd_client
from . import synchronize_service


class CommandModule(Protocol):
    name: str
    title: str

    def setup(self, parser: argparse.ArgumentParser) -> None:
        ...

    async def main(
        self, critic: api.critic.Critic, arguments: argparse.Namespace
    ) -> int:
        ...


modules = cast(
    Sequence[CommandModule],
    [
        addextension,
        addrepository,
        addrole,
        adduser,
        configuration,
        connect,
        delrole,
        deluser,
        disconnect,
        interactive,
        listusers,
        lookup_ssh_key,
        passwd,
        run_extensionhost,
        run_frontend,
        run_services,
        run_sshd,
        run_task,
        run_worker,
        send_email,
        settings,
        sshd_client,
        synchronize_service,
    ],
)
