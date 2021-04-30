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
import asyncio
import json
import logging
import os
from typing import BinaryIO

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from critic.base import mimetype


class NotFound(Exception):
    pass


async def _serveFile(
    request: aiohttp.web.BaseRequest, path: str
) -> aiohttp.web.StreamResponse:
    home_dir = base.configuration()["paths.home"]
    ui_dir = os.path.join(home_dir, "ui")

    response = aiohttp.web.StreamResponse(
        headers={
            "content-type": mimetype.guess_from_filename(path),
            "last-modified": "Thu, 01 Jan 1970 00:00:00 GMT",
            "expires": "Tue, 01 Feb 2050 00:00:00 GMT",
            "cache-control": f"max-age={60 * 60 * 24 * 365 * 20}",
        }
    )

    async def send_file(file: BinaryIO) -> None:
        while True:
            data = file.read(2 ** 20)
            if not data:
                return
            await response.write(data)

    full_path = os.path.join(ui_dir, path)

    accept_encodings = {
        encoding.strip()
        for encoding in request.headers.get("accept-encoding", "").split(",")
        if encoding.strip()
    }

    if "br" in accept_encodings and os.path.isfile(full_path + ".br"):
        response.headers["content-encoding"] = "br"
        await response.prepare(request)
        with open(full_path + ".br", "rb") as file:
            await send_file(file)
        return response

    if "gzip" in accept_encodings and os.path.isfile(full_path + ".gz"):
        response.headers["content-encoding"] = "gzip"
        await response.prepare(request)
        with open(full_path + ".gz", "rb") as file:
            await send_file(file)
        return response

    if os.path.isfile(full_path):
        await response.prepare(request)
        with open(full_path, "rb") as file:
            await send_file(file)
        return response

    raise aiohttp.web.HTTPNotFound()


async def serveIndexHtml(
    critic: api.critic.Critic,
    request: aiohttp.web.BaseRequest,
) -> aiohttp.web.StreamResponse:
    from .preload import json_responses

    home_dir = base.configuration()["paths.home"]
    ui_dir = os.path.join(home_dir, "ui")

    try:
        with open(os.path.join(ui_dir, "index.html"), "rb") as index_html_file:
            index_html = index_html_file.read()
    except FileNotFoundError:
        raise NotFound()

    response = aiohttp.web.StreamResponse(
        headers={"content-type": "text/html; encoding=utf-8"}
    )

    await response.prepare(request)

    try:
        body_end_index = index_html.index(b"</body>")
    except ValueError:
        await response.write(index_html)
    else:
        await response.write(index_html[:body_end_index])

        try:
            preloaded = json.dumps(
                await json_responses(critic, request), separators=(",", ":")
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Preloading JSON responses failed")
            preloaded = ""

        await response.write(
            b'<script>window["preloaded"]=JSON.parse(%s)</script>%s'
            % (repr(preloaded).encode(), index_html[body_end_index:])
        )

    return response


async def serveStatic(request: aiohttp.web.BaseRequest) -> aiohttp.web.StreamResponse:
    assert request.path.startswith("/static/")
    return await _serveFile(request, request.path.lstrip("/"))