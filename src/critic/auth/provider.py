# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

from __future__ import annotations

import aiohttp.web
from abc import ABC, abstractmethod
from typing import Any, Dict, Mapping, Optional

from critic import api


class Provider(ABC):
    @staticmethod
    def enabled() -> Mapping[str, Provider]:
        from . import providers

        settings = api.critic.settings()
        result: Dict[str, Provider] = {}
        if settings:
            available = settings.authentication.external_providers
            # if base.configuration().get("system.is_testing"):
            #     for name in available.keys():
            #         if not getattr(available, name).enabled:
            #             continue
            #         result[name] = providers.dummy.DummyOAuthProvider(name)
            # else:
            if "github" in available and available.github.enabled:
                result["github"] = providers.github.GitHubAuthentication()
            if "google" in available and available.google.enabled:
                result["google"] = providers.google.GoogleAuthentication()
        return result

    @property
    def configuration(self) -> Any:
        providers = api.critic.settings().authentication.external_providers
        return getattr(providers, self.name)

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def getTitle(self) -> str:
        """Title, suitable as X in 'Sign in using your X'"""
        ...

    @abstractmethod
    def getAccountIdDescription(self) -> str:
        """Description of the value used as the account identifier"""
        ...

    def getAccountURL(self, account_id: str) -> Optional[str]:
        return None

    @abstractmethod
    async def start(
        self, critic: api.critic.Critic, req: aiohttp.web.BaseRequest
    ) -> None:
        ...

    @abstractmethod
    async def finish(
        self, critic: api.critic.Critic, req: aiohttp.web.BaseRequest
    ) -> None:
        ...
