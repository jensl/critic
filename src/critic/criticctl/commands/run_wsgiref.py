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
import wsgiref.simple_server

logger = logging.getLogger(__name__)

name = "run-wsgiref"
title = "Run wsgiref front-end"
long_description = """

This command starts a simple HTTP front-end using the wsgiref.simple_server
package. It's a very quick way to access Critic's web UI, but is only suitable
for testing/debugging purposes, since the started front-end will be
single-threaded.

The front-end is not daemonized; this command simply never exits until aborted,
e.g. by pressing CTRL-c.

"""


def setup(parser):
    parser.add_argument("--update-identity", help="Update the named system identity.")
    parser.add_argument(
        "--host",
        default="localhost",
        help='Host to listen at. Use "0.0.0.0" to listen at all interfaces.',
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="TCP port to listen at. Use 0 for a randomly assigned port.",
    )

    parser.set_defaults(need_session=True)


async def main(critic, arguments):
    class CriticWSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
        def log_message(self, *args, **kwargs):
            fmt, request_line, status, response_size = args
            logger.debug('"%s" => %s (%s bytes)', request_line, status, response_size)

    from ...wsgi.main import application

    server = wsgiref.simple_server.make_server(
        host=arguments.host,
        port=arguments.port,
        app=application,
        handler_class=CriticWSGIRequestHandler,
    )

    server_address = f"{server.server_name}:{server.server_port}"

    if arguments.update_identity:
        async with critic.transaction() as cursor:
            await cursor.execute(
                """UPDATE systemidentities
                      SET hostname=%s
                    WHERE key=%s""",
                (server_address, arguments.update_identity),
            )

    logger.info(f"Listening at {server_address}")

    try:
        # This call will never return normally.
        server.serve_forever()
    except KeyboardInterrupt:
        pass
