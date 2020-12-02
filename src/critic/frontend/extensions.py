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

import aiohttp.web
import logging
import secrets
from typing import Optional, Sequence, Tuple, Union

from multidict import CIMultiDict

logger = logging.getLogger(__name__)

from critic import api
from critic import frontend
from critic import pubsub

# from critic.background import extensiontasks
from critic.background.extensionhost import (
    CallResponse,
    EndpointRequest,
    EndpointResponseBodyFragment,
    EndpointResponseEnd,
    EndpointResponsePrologue,
    EndpointRole,
    CallRequest,
)


async def handle_endpoint(
    request: aiohttp.web.BaseRequest,
    installation: api.extensioninstallation.ExtensionInstallation,
    components: Sequence[str],
) -> aiohttp.web.StreamResponse:
    logger.debug("handle_endpoint: %r %r", installation, components)

    name = components[4]
    path = "/".join(components[5:])

    critic = installation.critic
    version = await installation.version
    manifest = await version.manifest
    for endpoint in manifest.endpoints:
        if endpoint.name == name:
            break
    else:
        raise aiohttp.web.HTTPNotFound(text=f"endpoint {name} not found")

    extension = await installation.extension

    def include_header(header: Tuple[str, str]) -> bool:
        name, _ = header
        if name.lower() in ("authorization", "cookie"):
            return False
        return True

    body: Optional[Union[bytes, str]]

    if request.can_read_body:
        try:
            body = await request.text()
        except ValueError:
            body = await request.read()
    else:
        body = None

    user_id = user.id if (user := critic.actual_user) else None

    async with pubsub.connect(
        f"extension endpoint: {await extension.key}::{name}"
    ) as client:
        request_id = secrets.token_bytes(8)
        call = await client.request(
            pubsub.Payload(
                CallRequest(
                    version.id,
                    user_id if user_id is not None else "anonymous",
                    token.id if (token := critic.access_token) else None,
                    EndpointRole(
                        name,
                        EndpointRequest(
                            request_id,
                            request.method,
                            path,
                            list(request.query.items()),
                            list(filter(include_header, request.headers.items())),
                            body,
                        ),
                    ),
                )
            ),
            pubsub.ChannelName("extension/call"),
        )
        await call.delivery
        call_response = await call.response

    assert isinstance(call_response, CallResponse)
    if not call_response.success:
        raise aiohttp.web.HTTPInternalServerError(text="¯\\_(ツ)_/¯")
    assert len(call_response.items) >= 2

    prologue = call_response.items[0]
    body_fragments = call_response.items[1:-1]
    end = call_response.items[-1]

    assert isinstance(prologue, EndpointResponsePrologue)
    response = aiohttp.web.StreamResponse(
        status=prologue.status_code,
        reason=prologue.status_text,
        headers=CIMultiDict(prologue.headers),
    )
    await response.prepare(request)

    for body_fragment in body_fragments:
        assert isinstance(body_fragment, EndpointResponseBodyFragment)
        await response.write(body_fragment.data)

    assert isinstance(end, EndpointResponseEnd)
    await response.write_eof()

    return response


# async def return_resource(req, installation, path, filename=None):
#     try:
#         resource = await extensiontasks.fetch_resource(
#             req.critic, await installation.extension, await installation.version, path
#         )
#     except extensiontasks.Error as error:
#         logger.exception("oh, no!")
#         raise request.InternalServerError(str(error))
#     logger.debug(repr(resource.data))
#     if filename is None:
#         filename = path
#     req.setContentType(base.mimetype.guess_from_filename(filename))
#     await req.start()
#     await req.write(resource.data)
#     return req.response


# async def handle_ui_addon(req, installation, components):
#     if len(components) != 6:
#         raise frontend.NotHandled
#     ui_addon_name, bundle_type = components[4:]
#     if bundle_type not in ("js", "css"):
#         raise request.BadRequest(f"Invalid bundle type: {bundle_type}")
#     manifest = await installation.manifest
#     for ui_addon in manifest.ui_addons:
#         if ui_addon.name != ui_addon_name:
#             continue
#         if bundle_type == "js":
#             if ui_addon.bundle_js is None:
#                 raise request.NotFound(
#                     f"UI addon `{ui_addon_name}` did not define a JS bundle"
#                 )
#             return await return_resource(req, installation, ui_addon.bundle_js)
#         if bundle_type == "css":
#             if ui_addon.bundle_css is None:
#                 raise request.NotFound(
#                     f"UI addon `{ui_addon_name}` did not define a CSS bundle"
#                 )
#             return await return_resource(req, installation, ui_addon.bundle_css)
#     else:
#         raise request.NotFound(f"UI addon `{ui_addon_name}` not defined")
#     raise frontend.NotHandled


# async def handle_resource(req, installation, components):
#     raise frontend.NotHandled


async def handle(
    critic: api.critic.Critic, request: aiohttp.web.BaseRequest
) -> aiohttp.web.StreamResponse:
    if not api.critic.settings().extensions.enabled:
        raise frontend.NotHandled
    components = request.path.strip("/").split("/")
    if len(components) < 4 or components[:2] != ["api", "x"]:
        raise frontend.NotHandled
    extension_name, request_type = components[2:4]
    if request_type not in ("endpoint", "uiaddon", "resource"):
        raise aiohttp.web.HTTPBadRequest(text=f"Invalid request type: {request_type}")
    installation = await api.extensioninstallation.fetch(
        critic, extension_name=extension_name, user=critic.effective_user
    )
    if not installation:
        logger.debug("extension not installed: %r", extension_name)
        raise aiohttp.web.HTTPNotFound(
            text=f"Extension `{extension_name}` not installed"
        )
    if request_type == "endpoint":
        return await handle_endpoint(request, installation, components)
    # if request_type == "uiaddon":
    #     return await handle_ui_addon(request, installation, components)
    # return await handle_resource(request, installation, components)
    raise frontend.NotHandled
