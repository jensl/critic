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
import logging
import os

logger = logging.getLogger(__name__)

from critic import base


class NotFound(Exception):
    pass


async def _serveFile(req, path):
    home_dir = base.configuration()["paths.home"]
    ui_dir = os.path.join(home_dir, "ui")

    req.setContentType(base.mimetype.guess_from_filename(path))

    async def send_file(file):
        while True:
            data = file.read(2 ** 20)
            if not data:
                return
            await req.write(data)

    full_path = os.path.join(ui_dir, path)

    accept_encodings = {
        encoding.strip()
        for encoding in req.getRequestHeader("Accept-Encoding", "").split(",")
        if encoding.strip()
    }

    if "br" in accept_encodings and os.path.isfile(full_path + ".br"):
        req.setContentEncoding("br")
        await req.start()
        with open(full_path + ".br", "rb") as file:
            await send_file(file)
        return req.response

    if "gzip" in accept_encodings and os.path.isfile(full_path + ".gz"):
        req.setContentEncoding("gzip")
        await req.start()
        with open(full_path + ".gz", "rb") as file:
            await send_file(file)
        return req.response

    if os.path.isfile(full_path):
        await req.start()
        with open(full_path, "rb") as file:
            await send_file(file)
        return req.response

    raise NotFound()


async def serveIndexHtml(req):
    from .preload import json_responses

    home_dir = base.configuration()["paths.home"]
    ui_dir = os.path.join(home_dir, "ui")

    try:
        with open(os.path.join(ui_dir, "index.html"), "rb") as index_html_file:
            index_html = index_html_file.read()
    except FileNotFoundError:
        raise NotFound()

    req.setContentType("text/html; encoding=utf-8")
    await req.start()

    try:
        body_end_index = index_html.index(b"</body>")
    except ValueError:
        await req.write(index_html)
    else:
        await req.write(index_html[:body_end_index])

        try:
            preloaded = json.dumps(await json_responses(req), separators=(",", ":"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Preloading JSON responses failed")
            preloaded = ""

        await req.write(
            b'<script>window["preloaded"]=JSON.parse(%s)</script>%s'
            % (repr(preloaded).encode(), index_html[body_end_index:])
        )


async def serveStatic(req):
    try:
        assert req.path.startswith("static/")
        req.cacheForever()
        return await _serveFile(req, req.path)
    except Exception:
        logger.exception("Failed to serve static file!")
