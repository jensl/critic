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

from __future__ import annotations

import argparse
import asyncio
import collections
import cProfile
import json
import logging
import multiprocessing
import os
import pstats
import signal
import sys
import tempfile
import traceback
from typing import Any

logger = logging.getLogger(__name__)

from critic import api


name = "run-frontend"
title = "Run HTTP front-end"
long_description = """

This command starts an HTTP front-end that serves Critic web UI. This is a quick
way to access Critic's web UI, but is maily suitable for testing/debugging, or
smaller production systems, since the started front-end will be single process,
and will thus not be able to truly serve requests in parallel on multi-CPU
systems.

The front-end is not daemonized; this command simply never exits until aborted,
e.g. by pressing CTRL-c.

Two flavors of HTTP front-end are supported:

  --flavor=wsgiref (default)

    Runs the server using the builtin wsgiref.simple_server package.

  --flavor=aiohttp

    Runs the server using the aiohttp package, which runs a single-process,
    single-threaded server that serves multiple requests in parallel via an
    `asyncio` event loop.

"""


def format_sockname(sockname: tuple) -> str:
    if len(sockname) == 2:
        # IPv4
        server_host, server_port = sockname
    elif len(sockname) == 4:
        # IPv6
        ipv6_address, server_port, _, _ = sockname
        server_host = f"[{ipv6_address}]"
    else:
        raise Exception("unsupported sockname: %r")

    return f"{server_host}:{server_port}"


async def server_started(critic, arguments, server_sockname):
    if len(server_sockname) != 2:
        return

    try:
        server_address = format_sockname(server_sockname)
    except Exception:
        logger.exception("Unsupported server socket name")
        return

    if arguments.update_identity:
        async with critic.transaction() as cursor:
            await cursor.execute(
                """UPDATE systemidentities
                      SET hostname={hostname}
                    WHERE key={identity}""",
                hostname=server_address,
                identity=arguments.update_identity,
            )

    logger.info(f"Listening at http://{server_address}")


async def run_wsgiref(critic, arguments, stopped):
    import wsgiref.simple_server

    from ...wsgi.main import application

    class CriticWSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
        def log_message(self, *args, **kwargs):
            fmt, request_line, status, response_size = args
            logger.debug('"%s" => %s (%s bytes)', request_line, status, response_size)

    server = wsgiref.simple_server.make_server(
        host=arguments.listen_host,
        port=arguments.port,
        app=application,
        handler_class=CriticWSGIRequestHandler,
    )

    await server_started(critic, arguments, (server.server_name, server.server_port))

    try:
        # This call will never return normally.
        server.serve_forever()
    except KeyboardInterrupt:
        pass


async def run_aiohttp(
    critic: api.critic.Critic, arguments: Any, stopped: asyncio.Event
) -> None:
    import aiohttp.web

    from ...wsgi.request import HTTPResponse, AIOHTTPRequest
    from critic import auth
    from critic import frontend
    from critic import jsonapi

    # from critic import resources

    loop = asyncio.get_event_loop()

    async def process_request(
        request: aiohttp.web.BaseRequest, req: AIOHTTPRequest
    ) -> aiohttp.web.StreamResponse:
        await auth.AccessControl.forRequest(req)
        await auth.AccessControl.accessHTTP(req)

        try:
            await frontend.externalauth.handle(req)
        except frontend.NotHandled:
            pass

        try:
            return await frontend.extensions.handle(req.critic, request)
        except frontend.NotHandled:
            pass

        try:
            return await frontend.download.handle(req)
        except frontend.NotHandled:
            pass

        if req.path.startswith("api/"):
            try:
                data = await jsonapi.handleRequest(req.critic, req)
            except jsonapi.Error as error:
                req.setStatus(error.http_status)
                data = error.as_json()
            try:
                data_json = json.dumps(data, indent=2)
            except TypeError:
                logger.error(repr(data))
                raise
            req.setContentType("application/json")
            await req.start()
            try:
                encoded = data_json.encode()
            except TypeError:
                logger.debug(repr(data_json))
                raise
            await req.write(encoded)
            return req.response

        if req.path == "ws":
            return await frontend.websocket.serve(req)

        if req.path.startswith("static/"):
            try:
                return await frontend.ui.serveStatic(req)
            except frontend.ui.NotFound:
                return aiohttp.web.Response(text="Not found", status=404)

        # if req.path.startswith("favicon."):
        #     req.setContentType("image/png")
        #     await req.start()
        #     await req.write(resources.fetch("favicon.png")[0])
        #     return req.response

        is_git_ua = req.getRequestHeader("User-Agent", "").startswith("git/")

        repository, path = await frontend.gitrepository.identifyFromRequest(
            req, require_suffix=not is_git_ua
        )
        if repository:
            try:
                await frontend.gitrepository.invokeHttpBackend(req, repository, path)
            except frontend.gitrepository.NeedsUser:
                raise aiohttp.web.HTTPUnauthorized(
                    text="Must be signed in",
                    headers={"WWW-Authenticate": 'Basic realm="Critic"'},
                )
            else:
                return req.response

        try:
            await frontend.ui.serveIndexHtml(req)
        except frontend.ui.NotFound:
            return aiohttp.web.Response(text="UI not available", status=404)
        else:
            return req.response

    async def handle_request(
        request: aiohttp.web.BaseRequest,
    ) -> aiohttp.web.StreamResponse:
        if arguments.profile:
            profile = cProfile.Profile()
            profile.enable()
        response = None
        try:
            async with api.critic.startSession(
                for_user=True, loop=request.loop
            ) as critic:
                async with AIOHTTPRequest(critic, request) as req:
                    try:
                        response = await process_request(request, req)
                    except HTTPResponse as http_response:
                        await http_response.execute(req)
                        response = req.response
                    except asyncio.CancelledError:
                        if not req.finished:
                            logger.debug("Request cancelled")
                        raise
        except auth.AccessDenied as error:
            return aiohttp.web.Response(text=str(error), status=403)
        except asyncio.CancelledError:
            raise
        except aiohttp.web.HTTPException:
            raise
        except Exception:
            logger.exception("Request failed")
            return aiohttp.web.Response(text=traceback.format_exc(), status=500)
        finally:
            if arguments.profile:
                profile.disable()
                stats = pstats.Stats(profile)
                stats.sort_stats("time")
                stats.print_callers(5)
        if response is None:
            logger.debug("no response returned")
            raise aiohttp.web.HTTPServiceUnavailable()
        return response

    async def start() -> None:
        from .. import as_root

        # class AccessHandler(logging.Handler):
        #     def emit(self, record: logging.LogRecord) -> None:
        #         logger.log(record.levelno, record.msg % record.args)
        # logging.getLogger("aiohttp.access").addHandler(AccessHandler())

        from aiohttp.abc import AbstractAccessLogger

        class AccessLogger(AbstractAccessLogger):
            def log(self, request, response, time):
                logger.info(
                    f"{request.remote} "
                    f'"{request.method} {request.path} '
                    f"done in {time}s: {response.status}"
                )

        protocol_factory = aiohttp.web.Server(
            handle_request, access_log_class=AccessLogger
        )

        if arguments.unix:
            server = await loop.create_unix_server(
                protocol_factory, path=arguments.unix
            )
        else:
            with as_root():
                server = await loop.create_server(
                    protocol_factory,
                    host=arguments.listen_host,
                    port=arguments.listen_port,
                )

            assert server.sockets

            for server_socket in server.sockets:
                await server_started(critic, arguments, server_socket.getsockname())

    # def dump_profiling_stats():
    #     profile.print_stats(sort="time")

    # if arguments.profile:
    #     loop.add_signal_handler(signal.SIGHUP, dump_profiling_stats)

    #     profile = cProfile.Profile()
    #     profile.enable()

    try:
        await start()
    except FileNotFoundError:
        # This can happen due to a race, when stopping the system during startup.
        if not stopped.is_set():
            raise

    await stopped.wait()


async def run_lb_frontend(critic, arguments, stopped):
    from .. import as_root

    worker_tasks = []
    worker_processes = []
    worker_paths = collections.deque()

    semaphore = asyncio.Semaphore(value=0)

    async def handle_client(client_reader, client_writer):
        async with semaphore:
            worker_path = worker_paths.popleft()
            worker_paths.append(worker_path)

        logger.debug(
            "handling client: %s -> %s",
            format_sockname(client_writer.get_extra_info("peername")),
            worker_path,
        )

        worker_reader, worker_writer = await asyncio.open_unix_connection(worker_path)

        async def forward(reader, writer):
            try:
                while True:
                    data = await reader.read(65536)
                    if not data:
                        raise ConnectionError
                    writer.write(data)
                    await writer.drain()
            except ConnectionError:
                try:
                    writer.write_eof()
                except OSError:
                    pass

        await asyncio.gather(
            forward(client_reader, worker_writer),
            forward(worker_reader, client_writer),
            return_exceptions=True,
        )

        async def close_stream(writer):
            writer.close()
            if hasattr(writer, "wait_closed"):
                await writer.wait_closed()

        await asyncio.gather(
            close_stream(worker_writer),
            close_stream(client_writer),
            return_exceptions=True,
        )

    async def check_backend(worker_path):
        import aiohttp

        try:
            connector = aiohttp.UnixConnector(path=worker_path)
            async with aiohttp.request(
                "GET",
                "http://localhost/api/v1/sessions/current",
                allow_redirects=False,
                connector=connector,
            ) as response:
                if response.status != 200:
                    raise Exception("Unexpected response from backend")
                await response.read()
        except Exception:
            logger.exception("Load balancer backend check failed!")
            return False
        else:
            return True
        finally:
            await connector.close()

    async def run_worker(index):
        worker_path = os.path.join(work_dir, "worker-%d.unix" % index)

        argv = [sys.argv[0]]
        if arguments.binary_output:
            argv.append("--binary-output")
        if arguments.loglevel < logging.INFO:
            argv.append("--verbose")
        elif arguments.loglevel > logging.INFO:
            argv.append("--quiet")

        argv.extend(
            [
                "run-frontend",
                "--worker",
                "--flavor",
                arguments.flavor,
                "--unix",
                worker_path,
            ]
        )
        if arguments.update_identity:
            argv.extend(["--update-identity", arguments.update_identity])
        if arguments.profile:
            argv.append("--profile")

        process = await asyncio.create_subprocess_exec(*argv)

        while not os.path.exists(worker_path):
            await asyncio.sleep(0.1)

        while not await check_backend(worker_path):
            await asyncio.sleep(0.5)

        worker_processes.append(process)
        worker_paths.append(worker_path)

        semaphore.release()

        logger.info("Started backend process [pid=%d]", process.pid)

        try:
            await process.wait()
        except asyncio.CancelledError:
            logger.info(" - terminating backend process [pid=%d]", process.pid)
            process.terminate()
        else:
            worker_processes.remove(process)
            worker_paths.remove(worker_path)
            await semaphore.acquire()

    async def start():
        for index in range(arguments.scale):
            worker_tasks.append(asyncio.ensure_future(run_worker(index)))

        if arguments.unix:
            server = await asyncio.start_unix_server(handle_client, path=arguments.unix)

            if arguments.unix_socket_owner:
                with as_root():
                    chown = await asyncio.create_subprocess_exec(
                        "chown", arguments.unix_socket_owner, arguments.unix
                    )
                    await chown.wait()
        else:
            with as_root():
                server = await asyncio.start_server(
                    handle_client,
                    host=arguments.listen_host,
                    port=arguments.listen_port,
                )

            for socket in server.sockets:
                await server_started(critic, arguments, socket.getsockname())

    async def stop():
        logger.info("Stopping load balancer")
        for task in worker_tasks:
            if not task.done():
                task.cancel()
        await asyncio.wait(worker_tasks)
        logger.info("Load balancer stopped")

    with tempfile.TemporaryDirectory() as work_dir:
        await start()
        await stopped.wait()
        await stop()


def setup(parser):
    parser.add_argument(
        "--flavor",
        choices=("wsgiref", "aiohttp"),
        default="aiohttp",
        help="Flavor of HTTP server to run.",
    )
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
    parser.add_argument(
        "--unix", help="UNIX domain socket path. If used, --host/--port are ignored."
    )
    parser.add_argument(
        "--unix-socket-owner",
        help=(
            "Assign ownership of the UNIX socket to user:group. If running "
            "behind a local reverse proxy, www-data:www-data might be "
            "appropriate, for instance."
        ),
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help=(
            "Enable profiling. Output is printed to stderr when SIGHUP is " "received."
        ),
    )

    scaling = parser.add_argument_group("Scaling")
    scaling.add_argument(
        "--scale",
        type=int,
        default=multiprocessing.cpu_count(),
        help=(
            "Number of back-end processes to start behind a simple load " "balancer."
        ),
    )
    scaling.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)

    load_balancer = parser.add_argument_group("Load balancer")
    load_balancer.add_argument(
        "--announce-backend",
        action="store_true",
        help="Announce backend for dynamic load balancer.",
    )

    parser.set_defaults(need_session=True)


async def main(critic, arguments):
    stopped = asyncio.Event()

    def stop():
        stopped.set()

    critic.loop.add_signal_handler(signal.SIGINT, stop)
    critic.loop.add_signal_handler(signal.SIGTERM, stop)

    if arguments.scale and not arguments.worker:
        await run_lb_frontend(critic, arguments, stopped)
    elif arguments.flavor == "wsgiref":
        await run_wsgiref(critic, arguments, stopped)
    else:
        await run_aiohttp(critic, arguments, stopped)
