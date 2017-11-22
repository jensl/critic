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
import contextlib
import grp
import logging
import os
import pwd
import sys
import traceback
from typing import Callable, Optional

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from critic import dbaccess


is_virtualenv = sys.prefix != sys.base_prefix


def home_dir():
    return os.environ.get(
        "CRITIC_HOME", sys.prefix if is_virtualenv else "/var/lib/critic"
    )


def check_if_quickstarted():
    quickstart_pidfile = os.path.join(home_dir(), "quickstart.pid")
    return os.path.isfile(quickstart_pidfile)


is_quickstarted = None


@contextlib.contextmanager
def temporary_cwd(cwd, use_fallback=True):
    previous_cwd = os.getcwd()

    try:
        os.chdir(cwd)
    except OSError:
        if not use_fallback:
            raise
        os.chdir("/")

    try:
        yield
    finally:
        os.chdir(previous_cwd)


class InvalidUser(Exception):
    pass


@contextlib.contextmanager
def as_user(*, uid=None, name=None):
    assert (uid is None) != (name is None)

    if uid is not None:
        pwentry = pwd.getpwuid(uid)
    else:
        try:
            pwentry = pwd.getpwnam(name)
        except KeyError:
            raise InvalidUser("%s: no such user" % name) from None

    if uid == os.geteuid() or os.getuid() != 0:
        yield lambda: None
        return

    previous_euid = os.geteuid()

    try:
        os.seteuid(pwentry.pw_uid)
    except OSError as error:
        logger.error("Failed to set effective uid: %s", error)
        sys.exit(1)

    def restore_user():
        nonlocal previous_euid
        if previous_euid is not None:
            os.seteuid(previous_euid)
            previous_euid = None

    with temporary_cwd(pwentry.pw_dir):
        try:
            yield restore_user
        finally:
            restore_user()


@contextlib.contextmanager
def as_root():
    if is_quickstarted:
        yield
        return

    euid = os.geteuid()
    egid = os.getegid()

    try:
        os.seteuid(0)
        os.setegid(0)
    except OSError as error:
        logger.error("Failed to set effective uid/gid: %s", error)
        sys.exit(1)

    try:
        yield
    finally:
        os.setegid(egid)
        os.seteuid(euid)


class Outputter:
    emit: Optional[Callable[[str], None]]

    def __init__(self):
        self.emit = None

    def print(self, data: str) -> None:
        if self.emit:
            self.emit(data)
        else:
            print(data)


async def run(
    *, configuration: base.Configuration = None, critic: api.critic.Critic = None
) -> int:
    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter):
        def add_text(self, text: Optional[str]) -> None:
            if text is not None:
                for paragraph in text.split("\n\n"):
                    super().add_text(paragraph)

    title = "Critic administration interface"
    outputter = Outputter()

    parser = argparse.ArgumentParser(description=title, formatter_class=CustomFormatter)
    parser.set_defaults(stdout=outputter)

    output = parser.add_argument_group("Output options")
    output.add_argument(
        "--verbose",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        help="Enable debug output.",
    )
    output.add_argument(
        "--quiet",
        action="store_const",
        dest="loglevel",
        const=logging.WARNING,
        help="Disable purely informative output.",
    )
    output.add_argument("--color", action="store_const", const=True, dest="color")
    output.add_argument("--no-color", action="store_const", const=False, dest="color")
    output.add_argument("--binary-output", action="store_true", help=argparse.SUPPRESS)

    parser.set_defaults(
        loglevel=logging.INFO,
        color=False,
        configuration=configuration,
        critic=critic,
        is_quickstarted=is_quickstarted,
        must_be_root=not is_quickstarted,
    )

    subparsers = parser.add_subparsers(metavar="COMMAND", help="Command to perform.")

    from . import commands

    for module in commands.modules:
        if getattr(module, "disabled", False):
            continue

        if not configuration:
            if not getattr(module, "allow_missing_configuration", False):
                continue

        name = getattr(module, "name")
        title = getattr(module, "title")
        setup = getattr(module, "setup")
        main = getattr(module, "main")

        long_description = f"Critic administration interface: {title}"

        if hasattr(module, "long_description"):
            long_description += "\n\n" + getattr(module, "long_description").strip()

        subparser = subparsers.add_parser(
            name,
            description=long_description,
            help=title,
            formatter_class=CustomFormatter,
        )
        subparser.set_defaults(
            configuration=configuration, critic=critic, command_main=main
        )
        setup(subparser)

    arguments = parser.parse_args()

    class LevelFilter(logging.Filter):
        def __init__(self, predicate):
            self.predicate = predicate

        def filter(self, record):
            return self.predicate(record.levelno)

    root_logger = logging.getLogger()
    root_logger.setLevel(arguments.loglevel)

    # logging.getLogger("passlib").setLevel(logging.WARNING)

    if arguments.binary_output:
        from critic.base import binarylog

        binary_handler = binarylog.BinaryHandler(sys.stdout.buffer)
        root_logger.addHandler(binary_handler)

        outputter.emit = lambda data: binary_handler.write({"stdout": data})
    else:
        from critic.base import coloredlog

        log_format = "%(levelname)7s  %(message)s"
        formatter: Optional[logging.Formatter] = None

        if arguments.color is not False:
            colored_formatter = coloredlog.Formatter(log_format)
            if arguments.color is True or colored_formatter.is_supported():
                formatter = colored_formatter

        if formatter is None:
            formatter = logging.Formatter(log_format)

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.addFilter(LevelFilter(lambda level: level <= logging.INFO))
        stdout_handler.setFormatter(formatter)
        root_logger.addHandler(stdout_handler)

        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.addFilter(LevelFilter(lambda level: level > logging.INFO))
        stderr_handler.setFormatter(formatter)
        root_logger.addHandler(stderr_handler)

    if not hasattr(arguments, "command_main"):
        parser.print_help()
        return 0

    must_be_root = arguments.must_be_root

    if not critic and not is_quickstarted:
        must_be_root = True

    if must_be_root and os.getuid() != 0:
        logger.error("This script must be run as root!")
        return 1

    if not (
        getattr(arguments, "run_as_root", False)
        or getattr(arguments, "run_as_anyone", False)
        or not configuration
    ):
        critic_uid = pwd.getpwnam(configuration["system.username"]).pw_uid
        critic_gid = grp.getgrnam(configuration["system.groupname"]).gr_gid
        try:
            os.setegid(critic_gid)
            os.seteuid(critic_uid)
        except OSError as error:
            if os.getuid() != 0:
                logger.error("This script must be run as root!")
            else:
                logger.error("Failed to set effective uid/gid: %s", error)
            return 1

    async def apply(function, *args):
        result = function(*args)
        if asyncio.iscoroutine(result):
            return await result
        return result

    if getattr(arguments, "need_session", False):
        if critic is None:
            logger.error("Need session!")
            return 1

    returncode = await apply(arguments.command_main, critic, arguments)

    if returncode is None:
        returncode = 0

    return returncode


async def bootstrap():
    global is_quickstarted

    is_quickstarted = check_if_quickstarted()

    try:
        configuration = base.configuration()
    except base.MissingConfiguration:
        configuration = None

    async def run_with_session(restore_user):
        async with api.critic.startSession(for_system=True) as critic:
            restore_user()
            return await run(configuration=configuration, critic=critic)

    try:
        if configuration is None:
            return await run()

        try:
            with as_user(name=configuration["system.username"]) as restore_user:
                return await run_with_session(restore_user)
        except InvalidUser:
            return await run()
    finally:
        await dbaccess.shutdown()


def main():
    return asyncio.get_event_loop().run_until_complete(bootstrap())
