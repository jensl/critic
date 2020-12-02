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
from typing import Protocol, Sequence, cast

logger = logging.getLogger(__name__)

from critic import api
from . import install
from . import install_systemd_service
from . import upgrade
from . import frontend_nginx
from . import frontend_uwsgi
from . import container_uwsgi
from . import container_aiohttp
from . import calibrate_pwhash
from . import download_ui
from . import generate_extensions_profile
from .utils import TaskFailed


class TaskModule(Protocol):
    name: str
    description: str

    def setup(self, parser: argparse.ArgumentParser) -> None:
        ...

    async def main(
        self, critic: api.critic.Critic, arguments: argparse.Namespace
    ) -> int:
        ...


modules = cast(
    Sequence[TaskModule],
    [
        install,
        install_systemd_service,
        upgrade,
        frontend_nginx,
        frontend_uwsgi,
        container_uwsgi,
        container_aiohttp,
        calibrate_pwhash,
        download_ui,
        generate_extensions_profile,
    ],
)

__all__ = ["TaskFailed"]
