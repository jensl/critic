# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

import asyncio
import json
import logging
import os
import signal
import stat
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

from critic import api
from critic import base


class ServiceError(Exception):
    pass


class TimeoutError(Exception):
    pass


_running_service_name: Optional[str] = None


def is_background_service(service_name: str = None) -> bool:
    if service_name is None:
        return _running_service_name is not None
    return service_name == _running_service_name


def is_services() -> bool:
    if is_background_service():
        return True
    if base.configuration()["system.flavor"] in ("monolithic", "services"):
        return True
    return False


def service_address(service_name: str) -> str:
    return os.path.join(
        base.configuration()["paths.runtime"], "sockets", service_name + ".unix"
    )


def service_pidfile(service_name: str) -> str:
    return os.path.join(base.configuration()["paths.runtime"], service_name + ".pid")


def ensure_service(service_name: str) -> str:
    socket_path = service_address(service_name)

    try:
        if not stat.S_ISSOCK(os.stat(socket_path).st_mode):
            raise OSError
    except OSError:
        raise ServiceError("Service not running: %s" % service_name)

    return socket_path


async def issue_command(
    critic: api.critic.Critic, service_name: str, command: Any, timeout: float = None
) -> Any:
    async def communicate() -> Any:
        reader, writer = await asyncio.open_unix_connection(
            ensure_service(service_name)
        )

        writer.write(json.dumps(command).encode())
        writer.write_eof()

        data = await reader.read()

        return json.loads(data.decode())

    try:
        return await asyncio.wait_for(communicate(), timeout)
    except asyncio.TimeoutError:
        raise TimeoutError()


class WakeUpError(Exception):
    pass


async def wakeup(service_name: str, timeout: float = 3) -> bool:
    from .messagechannel import MessageChannel
    from .gateway import WakeUpRequest, Response

    gateway_settings = api.critic.settings().services.gateway

    if gateway_settings.enabled and not is_background_service():
        channel = MessageChannel[WakeUpRequest, Response]("gateway")

        await channel.write_message(
            WakeUpRequest(gateway_settings.secret, service_name)
        )

        async def read_response() -> bool:
            async for response in channel:
                if not isinstance(response, Response):
                    logger.warning(
                        "Unexpected response from gateway service: %r", response
                    )
                    return False
                if response.status != "ok":
                    logger.warning("Failed to wake up service: %s", response.message)
                    return False
                return True
            logger.warning("Connection closed prematurely")
            return False

        try:
            return await asyncio.wait_for(read_response(), timeout)
        except asyncio.TimeoutError:
            logger.warning("Timeout waking up service: %s", service_name)
            return False
    else:
        return wakeup_direct(service_name)


def wakeup_direct(service_name: str) -> bool:
    if not is_services():
        gateway_settings = api.critic.settings().services.gateway
        assert not gateway_settings.enabled

    pidfile_path = service_pidfile(service_name)
    try:
        with open(pidfile_path, "r", encoding="ascii") as pidfile:
            pid = int(pidfile.read().strip())
        logger.debug("waking up service: %s [pid=%d]", service_name, pid)
        os.kill(pid, signal.SIGHUP)
    except FileNotFoundError:
        # Service is not running. Might be perfectly normal (i.e. disabled
        # mail delivery.)
        raise WakeUpError(f"Background service not running: {service_name}") from None
    except ProcessLookupError:
        # The process id is not valid. So probably the background service has
        # crashed.
        raise WakeUpError(f"Background service has crashed: {service_name}") from None
    except Exception as error:
        raise WakeUpError(
            f"Crashed trying to wake up background service: {service_name}"
        ) from error
    return True
