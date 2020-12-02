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
import io
import logging
from typing import Optional, Tuple

from multidict import CIMultiDict

logger = logging.getLogger(__name__)

from critic import api


async def identifyFromRequest(
    critic: api.critic.Critic, req: aiohttp.web.BaseRequest, *, require_suffix: bool
) -> Tuple[Optional[api.repository.Repository], Optional[str]]:
    components = req.path.lstrip("/").split("/")
    for index in range(1, len(components) + 1):
        repository_path = "/".join(components[:index])
        additional_path = "/".join(components[index:])

        if not require_suffix and not repository_path.endswith(".git"):
            repository_path += ".git"

        if repository_path.endswith(".git"):
            try:
                repository = await api.repository.fetch(critic, path=repository_path)
            except api.repository.InvalidRepositoryPath:
                pass
            else:
                return repository, additional_path

    return None, None


class NeedsUser(Exception):
    pass


async def invokeHttpBackend(
    critic: api.critic.Critic,
    req: aiohttp.web.BaseRequest,
    repository: api.repository.Repository,
    path: str,
) -> aiohttp.web.StreamResponse:
    environ = {
        "GIT_HTTP_EXPORT_ALL": "true",
        "REMOTE_ADDR": req.remote,
        "PATH_INFO": req.path,
        # "PATH_TRANSLATED": os.path.join(repository.path, path),
        "REQUEST_METHOD": req.method,
        "QUERY_STRING": req.query_string,
    }

    if req.can_read_body:
        environ["CONTENT_TYPE"] = req.content_type

    for name, value in req.headers.items():
        environ[f"HTTP_{name.upper().replace('-', '_')}"] = value

    if "HTTP_CONTENT_ENCODING" in environ:
        del environ["HTTP_CONTENT_ENCODING"]
        if "HTTP_CONTENT_LENGTH" in environ:
            del environ["HTTP_CONTENT_LENGTH"]

    user = critic.effective_user

    if user.is_regular:
        environ["REMOTE_USER"] = user.name

    logger.debug("environment: %r", environ)

    needs_user = False
    response: Optional[aiohttp.web.StreamResponse] = None

    async def handle_headers(headers_data: io.BytesIO) -> None:
        nonlocal needs_user, response
        status: Optional[int] = 200
        reason: Optional[str] = "OK"
        headers = CIMultiDict[str]()
        for header in headers_data:
            logger.debug("header: %r", header)
            name, _, value = header.strip().partition(b":")
            name = name.strip()
            value = value.strip()
            if name.lower() == b"status":
                status_code_text, _, reason_text = value.partition(b" ")
                status_code = int(status_code_text, base=10)
                if status_code == 403 and user.is_anonymous:
                    needs_user = True
                status = status_code
                reason = str(reason_text.strip(), encoding="ascii")
            elif name.lower() == b"content-type":
                headers["content-type"] = str(value, encoding="ascii")
            else:
                headers[str(name, encoding="ascii")] = str(value, encoding="ascii")
        if not needs_user:
            logger.debug("starting response")
            assert isinstance(status, int)
            assert isinstance(reason, str)
            response = aiohttp.web.StreamResponse(
                status=status, reason=reason, headers=headers
            )
            await response.prepare(req)

    logger.info("Running 'git http-backend': %s %s", req.method, req.url)
    logger.debug("Repository: %s", repository.path)

    loop = critic.loop
    input_queue: "asyncio.Queue[bytes]" = asyncio.Queue(loop=loop)
    output_queue: "asyncio.Queue[bytes]" = asyncio.Queue(loop=loop)

    async def write_input():
        while True:
            data: bytes = await req.content.read(65536)
            await input_queue.put(data)
            if not data:
                break

    async def read_output():
        buffered = io.BytesIO()
        while True:
            data = await output_queue.get()
            if not data:
                break
            if response is None and not needs_user:
                try:
                    headers_end = data.index(b"\r\n\r\n")
                except ValueError:
                    buffered.write(data)
                    continue
                buffered.write(data[:headers_end])
                buffered.seek(0)
                await handle_headers(buffered)
                data = data[headers_end + 4 :]
            if response is not None and data:
                await response.write(data)
        if response is not None:
            await response.write_eof()

    tasks = [
        repository.low_level.stream("http-backend", input_queue, output_queue, environ),
        read_output(),
    ]

    if req.method in ("POST", "PUT"):
        tasks.append(write_input())
    else:
        await input_queue.put(b"")

    await asyncio.gather(*tasks, loop=loop)

    logger.debug("tasks done: %r", response)

    if needs_user:
        raise NeedsUser()

    assert response is not None
    return response
