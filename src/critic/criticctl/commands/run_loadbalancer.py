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

import aiohttp
import aiohttp.web
import asyncio
import logging
import os
import signal
from collections import deque

logger = logging.getLogger(__name__)

from critic import base
from critic.base import asyncutils
from critic import pubsub

name = "run-loadbalancer"
title = "Run front-end load-balancer"


class Backend:
    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.origin = f"http://{host}"
        if port != 80:
            self.origin += f":{port}"

        self.connector = aiohttp.TCPConnector(limit=None)

    def __eq__(self, other):
        return (self.host, self.port) == (other.host, other.port)

    def __str__(self):
        return f"{self.host}:{self.port}"


class BackendFailure(Exception):
    pass


class Backends:
    def __init__(self):
        self.__backends = deque()
        self.__semaphore = asyncio.Semaphore(value=0)

    def __contains__(self, backend):
        return backend in self.__backends

    def add(self, backend):
        assert backend not in self.__backends
        self.__backends.append(backend)
        self.__semaphore.release()

    @asyncutils.contextmanager
    async def get(self):
        await self.__semaphore.acquire()
        backend = self.__backends.popleft()
        try:
            yield backend
        except BackendFailure:
            logger.warning("Backend failed: %s", backend)
        else:
            self.__backends.append(backend)
            self.__semaphore.release()


backends = Backends()


def setup(parser):
    parser.add_argument("--update-identity", help="Update the named system identity.")
    parser.add_argument(
        "--listen-host",
        help=(
            "Host (i.e. interface) to listen at. If omitted, all interfaces "
            "are listened at."
        ),
    )
    parser.add_argument(
        "--listen-port",
        type=int,
        default=80,
        help=(
            "TCP port to listen at. Use --listen-port=0 for a randomly "
            "assigned port."
        ),
    )

    parser.set_defaults(need_session=True)


async def backend_announced(channel_name, message):
    if "backend" not in message:
        return

    logger.debug("backend announcement: %r", message)

    for host, port in message["backend"]["ipv4"]:
        backend = Backend(host, port)
        if backend in backends:
            continue
        backends.add(backend)


async def discover_backends(critic):
    while True:
        async with pubsub.connect("criticctl run-frontend") as pubsub_client:
            await pubsub_client.subscribe("$$$/apibackends", backend_announced)
            await pubsub_client.publish({"discover": True}, "$$$/apibackends")
            await pubsub_client.closed


class StaticFiles:
    def __init__(self):
        self.__files = {}

    def __contains__(self, path):
        return path in self.__files

    def __getitem__(self, path):
        return self.__files[path]

    def scan(self):
        ui_dir = os.path.join(base.configuration()["paths.home"], "ui")
        for dirpath, _, filenames in os.walk(ui_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                urlpath = "/" + os.path.relpath(filepath, ui_dir)
                with open(filepath, "rb") as file:
                    self.__files[urlpath] = file.read()
                logger.debug("%s: %d bytes", urlpath, len(self.__files[urlpath]))


static_files = StaticFiles()
content_types = {
    "css": "text/css; charset=utf-8",
    "eot": "application/vnd.ms-fontobject",
    "js": "application/javascript; charset=utf-8",
    "png": "image/png",
    "svg": "image/xml+svg",
    "ttf": "application/font-sfnt",
    "woff": "application/font-woff",
    "woff2": "font/woff2",
}


async def handle_static_file(request):
    _, slash, filename = request.path.rpartition("/")
    _, period, extension = filename.rpartition(".")
    if slash and period and extension in content_types:
        content_type = content_types[extension]
    else:
        content_type = "application/octet-stream"

    headers = {
        "Cache-Control": "public, max-age=157680000",
        "Content-Type": content_type,
        "Server": "Critic",
    }

    accept_encoding = request.headers.get("Accept-Encoding")
    if accept_encoding:
        accepted_encodings = [token.strip() for token in accept_encoding.split(",")]
    else:
        accepted_encodings = []

    if "br" in accepted_encodings:
        br_path = request.path + ".br"
        if br_path in static_files:
            headers.update({"Content-Encoding": "br"})
            return aiohttp.web.Response(body=static_files[br_path], headers=headers)

    if "gzip" in accepted_encodings:
        gzip_path = request.path + ".gzip"
        if gzip_path in static_files:
            headers.update({"Content-Encoding": "gzip"})
            return aiohttp.web.Response(body=static_files[br_path], headers=headers)

    return aiohttp.web.Response(body=static_files[request.path], headers=headers)


async def handle_websocket(session, origin, request):
    ws_client = aiohttp.web.WebSocketResponse(protocols=("pubsub_1",))

    await ws_client.prepare(request)

    async def forward_ws(x, source, destination):
        while True:
            message = await source.receive()
            if message.type == aiohttp.WSMsgType.CLOSING:
                return
            if message.type == aiohttp.WSMsgType.CLOSED:
                await destination.close()
                return
            if message.type == aiohttp.WSMsgType.TEXT:
                await destination.send_str(message.data)

    async with session:
        async with session.ws_connect(
            f"{origin}/ws", protocols=("pubsub_1",)
        ) as ws_backend:
            done, pending = await asyncio.wait(
                [
                    forward_ws("from client", ws_client, ws_backend),
                    forward_ws("from backend", ws_backend, ws_client),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                try:
                    task.result()
                except Exception:
                    logger.exception("WebSocket task failed")

            for task in pending:
                task.cancel()

    return ws_client


async def handle_request(request):
    if request.path in static_files:
        return await handle_static_file(request)

    async with backends.get() as backend:
        session = aiohttp.ClientSession(
            connector=backend.connector, connector_owner=False
        )
        origin = backend.origin

    if request.path == "/ws":
        return await handle_websocket(session, origin, request)

    async with session:
        headers = {}
        if "Cookie" in request.headers:
            headers["Cookie"] = request.headers["Cookie"]
        data = (await request.read()) if request.can_read_body else None
        async with session.request(
            method=request.method,
            url=f"{backend.origin}{request.rel_url}",
            data=data,
            headers=headers,
        ) as response:
            proxied_response = aiohttp.web.StreamResponse(
                status=response.status, reason=response.reason
            )
            proxied_response.headers.update(response.headers)
            proxied_response.headers["Server"] = "Critic"

            await proxied_response.prepare(request)

            async for data, _ in response.content.iter_chunks():
                await proxied_response.write(data)

            await proxied_response.write_eof()

    return proxied_response


async def start_server(critic, arguments):
    from .. import as_root

    protocol_factory = aiohttp.web.Server(handle_request)

    with as_root():
        server = await critic.loop.create_server(
            protocol_factory, host=arguments.listen_host, port=arguments.listen_port
        )

    for socket in server.sockets:
        # await server_started(critic, arguments, socket.getsockname())
        logger.debug(socket.getsockname())


async def main(critic, arguments):
    stopped = asyncio.Event()

    critic.loop.add_signal_handler(signal.SIGINT, stopped.set)
    critic.loop.add_signal_handler(signal.SIGTERM, stopped.set)

    static_files.scan()

    def server_started(future):
        try:
            future.result()
        except Exception:
            logger.exception("Failed to start server!")
            stopped.set()

    asyncio.ensure_future(start_server(critic, arguments)).add_done_callback(
        server_started
    )

    done, pending = await asyncio.wait(
        [discover_backends(critic), stopped.wait()], return_when=asyncio.FIRST_COMPLETED
    )

    for task in done:
        try:
            task.result()
        except Exception:
            logger.exception("Task crashed!")

    for task in pending:
        task.cancel()
