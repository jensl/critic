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
import contextlib
import distutils
import logging
import os
import signal
import tempfile

logger = logging.getLogger(__name__)

name = "run-httpd"
title = "Start the Apache HTTP server as a load balancer front-end"
long_description = """

This command runs the Apache HTTP server as a child process, with a suitable
generated configuration file.

"""

from critic import pubsub

modules = {
    "authz_core",
    "deflate",
    "env",
    "expires",
    "filter",
    "headers",
    "lbmethod_byrequests",
    "log_config",
    "logio",
    "mime",
    "mpm_event",
    "proxy",
    "proxy_balancer",
    "proxy_http",
    "proxy_wstunnel",
    "reqtimeout",
    "rewrite",
    "slotmem_shm",
    "unixd",
}


def setup(parser):
    parser.add_argument("--server-admin", required=True, help="Server administrator.")
    parser.add_argument("--server-name", required=True, help="Server hostname.")
    parser.add_argument(
        "--listen-host", help="Listen address. By default, listen on all interfaces."
    )
    parser.add_argument("--listen-port", type=int, default=80, help="Listen port.")

    parser.add_argument_group("Paths")

    httpd = distutils.spawn.find_executable("httpd")

    parser.add_argument(
        "--with-httpd",
        dest="httpd",
        metavar="PATH",
        default=httpd,
        required=httpd is None,
        help="Path to 'httpd' executable",
    )
    parser.add_argument(
        "--modules-dir",
        default="/usr/lib/apache2/modules",
        help="Path to directory containing Apache's modules",
    )

    parser.add_argument_group("Apache HTTP server modules")

    parser.add_argument(
        "--with-module",
        dest="with_modules",
        metavar="MODULE",
        action="append",
        default=[],
        help=(
            "Load an extra module. The argument value should be "
            "'foo' to load the module 'mod_foo.so'."
        ),
    )
    parser.add_argument(
        "--without-module",
        dest="without_modules",
        metavar="MODULE",
        action="append",
        default=[],
        help=(
            "Skip loading a module. The argument value should be 'foo' to "
            "load the module 'mod_foo.so'."
        ),
    )

    parser.set_defaults(run_as_root=True)


class Backend:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def __hash__(self):
        return hash((self.host, self.port))

    def __eq__(self, other):
        return self.host == other.host and self.port == other.port


def generate_configuration(critic, arguments, work_dir, backends):
    configuration = ""
    indentation_level = 0

    def indentation():
        return "    " * indentation_level

    @contextlib.contextmanager
    def block(comment=None):
        nonlocal configuration
        assert not configuration or configuration[-1] == "\n"
        if configuration and configuration[-2] not in ">\n":
            configuration += "\n"
        if comment is not None:
            configuration += f"{indentation()}# {comment}\n"
        yield
        configuration += "\n"

    @contextlib.contextmanager
    def section(**kwargs):
        nonlocal configuration, indentation_level
        assert len(kwargs) == 1
        [(section_name, value)] = kwargs.items()
        if value is None:
            value = ""
        else:
            value = f" {value}"
        with block():
            configuration += f"{indentation()}<{section_name}{value}>\n"
            indentation_level += 1
            yield
            indentation_level -= 1
            if configuration.endswith("\n\n"):
                configuration = configuration[:-1]
            configuration += f"{indentation()}</{section_name}>\n"

    def write_option(**kwargs):
        nonlocal configuration
        assert len(kwargs) == 1
        [(option_name, value)] = kwargs.items()

        def maybe_quote(value):
            if " " in value:
                return f'"{value}"'
            return value

        if isinstance(value, list):
            value = " ".join(maybe_quote(item) for item in value)
        else:
            value = maybe_quote(value)
        configuration += f"{indentation()}{option_name} {value}\n"

    def rewrite_precompressed(encoding_name, extension):
        write_option(RewriteCond=["%{HTTP:Accept-Encoding}", encoding_name])
        write_option(RewriteCond=[r"%{REQUEST_FILENAME}\." + extension, "-s"])
        write_option(
            RewriteRule=[r"^(.*)\.(js|css|map)$", "$1.$2." + extension, "[QSA]"]
        )

    with block():
        with_modules = set(arguments.with_modules)
        without_modules = set(arguments.without_modules)

        for module in sorted(modules | with_modules):
            try:
                without_modules.remove(module)
            except KeyError:
                pass
            else:
                continue
            write_option(
                LoadModule=[
                    f"{module}_module",
                    f"{arguments.modules_dir}/mod_{module}.so",
                ]
            )

        if without_modules:
            logger.warning("Superflouous --without-module arguments:")
            for module in sorted(without_modules):
                logger.warning(f"  --without-module={module}")

    with block():
        write_option(User="daemon")
        write_option(Group="daemon")

    if arguments.listen_host:
        listen_addr = f"{arguments.listen_host}:{arguments.listen_port}"
    else:
        listen_addr = f"{arguments.listen_port}"

    with block():
        write_option(Listen=listen_addr)
        write_option(ServerAdmin=arguments.server_admin)
        write_option(ServerName=arguments.server_name)
        write_option(ServerRoot=work_dir)
        write_option(DefaultRuntimeDir="run/")
        write_option(PidFile="run/httpd.pid")

    write_option(DocumentRoot="/var/lib/critic/ui")

    with section(Directory="/"):
        write_option(AllowOverride="none")
        write_option(Require=["all", "denied"])

    with section(Directory="/var/lib/critic/ui/static"):
        # write_option(AllowOverride="none")
        # write_option(Require=["method", "GET", "HEAD"])
        write_option(Require=["all", "granted"])

        with section(IfModule="rewrite_module"):
            write_option(RewriteEngine="on")

            with block("Handle precompressed files: brotli"):
                rewrite_precompressed("br", "br")
            with block("Handle precompressed files: gzip"):
                rewrite_precompressed("gzip", "gz")

            with block():
                write_option(
                    RewriteRule=[r"\.js\.(br|gz)$", "-", "[T=application/javascript]"]
                )
                write_option(RewriteRule=[r"\.css\.(br|gz)$", "-", "[T=text/css]"])

        with section(IfModule="expires_module"):
            write_option(ExpiresActive="on")
            write_option(ExpiresDefault="access plus 5 years")

    with block("Send error log to STDERR"):
        write_option(ErrorLog="/proc/self/fd/2")

    write_option(LogLevel="warn")

    with section(IfModule="log_config_module"):
        write_option(LogFormat=[r"%h %l %u %t \"%r\" %>s %b %I %O", "combinedio"])
        write_option(CustomLog=["/proc/self/fd/1", "combinedio"])

    with section(IfModule="headers_module"):
        write_option(RequestHeader=["unset", "Proxy", "early"])

    with open(os.path.join(work_dir, "mime.types"), "w") as mime_types:
        mime_types.write("application/javascript .js\n")
        mime_types.write("text/css .css\n")

    with section(IfModule="mime_module"):
        write_option(TypesConfig="mime.types")

    if backends:
        write_option(ProxyPass=["/static/", "!"])

        with section(Proxy="balancer://ws_backends"):
            for backend in backends:
                write_option(BalancerMember=[f"ws://{backend.host}:{backend.port}"])
        write_option(ProxyPass=["/ws", f"balancer://ws_backends/ws"])

        with section(Proxy="balancer://http_backends"):
            for backend in backends:
                write_option(BalancerMember=[f"http://{backend.host}:{backend.port}"])
        write_option(ProxyPass=["/", f"balancer://http_backends/"])
    else:
        logger.warning("No backends!")

    with section(IfModule="headers_module"):
        with section(FilesMatch=r"\.br$"):
            write_option(Header=["append", "Content-Encoding", "br"])
        with section(FilesMatch=r"\.gz$"):
            write_option(Header=["append", "Content-Encoding", "gzip"])

    logger.debug(configuration)

    configuration_filename = os.path.join(work_dir, "httpd.conf")
    with open(configuration_filename, "w") as configuration_file:
        configuration_file.write(configuration)

    return configuration_filename


async def run(critic, arguments, work_dir, stopped):
    httpd = None
    backends = set()
    scheduled_reload = None

    os.mkdir(os.path.join(work_dir, "run"))

    async def do_perform_reload():
        nonlocal httpd
        logger.info("Reloading server configuration")
        httpd_conf = generate_configuration(critic, arguments, work_dir, backends)
        if httpd is None:
            httpd = await asyncio.create_subprocess_exec(
                arguments.httpd, "-f", httpd_conf, "-D", "FOREGROUND"
            )

            def httpd_stopped(task):
                nonlocal httpd
                logger.info("Server exited with status %d", httpd.returncode)
                httpd = None
                schedule_reload()

            asyncio.ensure_future(httpd.wait()).add_done_callback(httpd_stopped)
        else:
            httpd.send_signal(signal.SIGUSR1)

    def perform_reload():
        def finished(task):
            if task:
                try:
                    task.result()
                except Exception:
                    logger.exception("Server reload failed unexpectedly!")

        asyncio.ensure_future(do_perform_reload()).add_done_callback(finished)

    def schedule_reload():
        nonlocal scheduled_reload
        if not scheduled_reload:
            scheduled_reload = critic.loop.call_later(1, perform_reload)

    async def do_find_backends():
        pubsub_client = pubsub.Client("criticctl run-httpd")

        def record_backend(channel_name, message):
            backend_data = message.get("backend")
            if backend_data:
                for host, port in backend_data["ipv4"]:
                    backend = Backend(host, port)
                    if backend not in backends:
                        logger.info("New backend advertised: %s:%d", host, port)
                        backends.add(backend)
                        schedule_reload()
                    else:
                        logger.debug(
                            "already known backend advertised: %s:%d", host, port
                        )

        await pubsub_client.ready
        await pubsub_client.subscribe("$$$/apibackends", record_backend)
        await pubsub_client.publish({"discover": True}, "$$$/apibackends")
        await pubsub_client.closed

    def find_backends():
        def finished(task):
            if task:
                try:
                    task.result()
                except Exception:
                    logger.exception("Backends search failed unexpectedly!")
                else:
                    logger.debug(
                        "backends search finished (pubsub service restarting?)"
                    )
                critic.loop.call_later(5, find_backends)

        asyncio.ensure_future(do_find_backends()).add_done_callback(finished)

    async def do_check_backends():
        for backend in backends.copy():
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host=backend.host, port=backend.port), 5
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Backend connection check timed out: %s:%d",
                    backend.host,
                    backend.port,
                )
            except OSError:
                logger.warning(
                    "Backend connection check failed: %s:%d", backend.host, backend.port
                )
            else:
                writer.close()
                continue

            backends.remove(backend)
            schedule_reload()

    def check_backends():
        def finished(task):
            if task:
                try:
                    task.result()
                except Exception:
                    logger.exception("Backends check failed unexpectedly!")
                critic.loop.call_later(60, check_backends)

        asyncio.ensure_future(do_check_backends()).add_done_callback(finished)

    # Initiate a backend search immediately.
    find_backends()

    # Perfom a "reload", which will actually start the server since it hasn't
    # been started yet. There will be no backends, so it can only serve static
    # files. But it will at least accept connections.
    perform_reload()

    # Schedule a (recurring) backend check.
    critic.loop.call_later(30, check_backends)

    await stopped.wait()


async def main(critic, arguments):
    stopped = asyncio.Event()

    def stop():
        stopped.set()

    critic.loop.add_signal_handler(signal.SIGINT, stop)
    critic.loop.add_signal_handler(signal.SIGTERM, stop)

    with tempfile.TemporaryDirectory() as work_dir:
        await run(critic, arguments, work_dir, stopped)
