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

from critic import api
from critic import base


class Provider:
    @staticmethod
    def enabled():
        from . import providers

        settings = api.critic.settings()
        result = {}
        if settings:
            available = settings.authentication.external_providers
            if base.configuration().get("system.is_testing"):
                for name in available.keys():
                    if not getattr(available, name).enabled:
                        continue
                    result[name] = providers.dummy.DummyOAuthProvider(name)
            else:
                if "github" in available and available.github.enabled:
                    result["github"] = providers.github.GitHubAuthentication()
                if "google" in available and available.google.enabled:
                    result["google"] = providers.google.GoogleAuthentication()
        return result

    @property
    def configuration(self):
        providers = api.critic.settings().authentication.external_providers
        return getattr(providers, self.name)

    def getTitle(self):
        """Title, suitable as X in 'Sign in using your X'"""
        pass

    def getAccountIdDescription(self):
        """Description of the value used as the account identifier"""
        pass

    def getAccountURL(self, account_id):
        return None

    def start(self, db, req, target_url=None):
        pass

    def finish(self, db, req):
        pass
