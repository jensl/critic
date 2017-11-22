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
import json

from .request import HTTPResponse, NotFound, WSGIRequest
from critic import api
from critic import auth
from critic import jsonapi


async def process_request(req):
    await auth.AccessControl.forRequest(req)
    await auth.AccessControl.accessHTTP(req)

    if req.path.startswith("api/"):
        try:
            data = await jsonapi.handleRequest(req.critic, req)
        except jsonapi.Error as error:
            req.setStatus(error.http_status)
            data = error.as_json()
        data_json = json.dumps(data)
        req.setContentType("application/json")
        await req.start()
        encoded = data_json.encode()
        return encoded

    raise NotFound()


async def handle_request(environ, start_response):
    async with api.critic.startSession(for_user=True) as critic:
        async with WSGIRequest(critic, environ, start_response) as req:
            try:
                return await process_request(req)
            except HTTPResponse as error:
                return await error.execute(req)


def application(environ, start_response):
    return asyncio.get_event_loop().run_until_complete(
        handle_request(environ, start_response)
    )
