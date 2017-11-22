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

logger = logging.getLogger(__name__)

from critic import auth
from critic import base
from critic import frontend
from critic.wsgi import request


def check_path(req):
    components = req.path.strip("/").split("/")
    if len(components) != 4 or components[:2] != ["api", "externalauth"]:
        raise frontend.NotHandled
    command = components[3]
    if command not in ("start", "finish"):
        raise request.BadRequest()
    provider_name = components[2]
    enabled_providers = auth.Provider.enabled()
    if not enabled_providers or not provider_name in enabled_providers:
        raise request.NotFound("Invalid authentication provider")
    return enabled_providers[provider_name], command


async def handle(req):
    provider, command = check_path(req)

    if command == "start":
        # This raises a redirect to the provider's authorization URL.
        await provider.start(req)
    else:
        try:
            # This raises a redirect to the target URL.
            await provider.finish(req)
        except (auth.InvalidRequest, auth.Failure) as error:
            # This is not really very helpful error handling. But it's not
            # expected that an actual failure to sign in will end up here;
            # presumably that error handling is taken care of at the
            # authentication provider's site.
            raise request.BadRequest(str(error))

    raise base.Error("Misbehaving authentication provider: " + provider.name)
