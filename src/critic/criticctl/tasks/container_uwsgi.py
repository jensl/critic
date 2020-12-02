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

import argparse
import distutils.spawn
import grp
import json
import logging
import multiprocessing
import os
import pwd
import subprocess
import tempfile

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from ..utils import as_root
from .utils import fail, install, service

TEMPLATE = """

[uwsgi]
plugins = python36

master = true
uwsgi-socket = %(sockets_dir)s/uwsgi.unix

# Change socket ownership so that the front-end can connect to it.
chown-socket = %(httpd_username)s:%(httpd_groupname)s
chmod-socket = 660

virtualenv = %(home_dir)s
module = critic.wsgi.main

processes = %(processes)d
threads = %(threads)d

# Run as the Critic system user/group.
uid = %(critic_username)s
gid = %(critic_groupname)s

"""

name = "container:uwsgi"
description = "Configure uWSGI as WSGI container."


def setup(parser: argparse.ArgumentParser) -> None:
    identity = parser.get_default("configuration")["system.identity"]

    deps_group = parser.add_argument_group("Dependencies")
    deps_group.add_argument(
        "--install-uwsgi",
        action="store_true",
        help="Install uWSGI on the system if it is missing.",
    )

    basic_group = parser.add_argument_group("Basic settings")
    basic_group.add_argument(
        "--processes",
        type=int,
        default=multiprocessing.cpu_count(),
        help="Number of processes to run.",
    )
    basic_group.add_argument(
        "--threads", type=int, default=1, help="Number of threads to run per process."
    )

    basic_group.add_argument(
        "--httpd-user", default="www-data", help="User that front-end runs as."
    )
    basic_group.add_argument(
        "--httpd-group", default="www-data", help="Group that front-end runs as."
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing app file instead of aborting.",
    )
    basic_group.add_argument(
        "--enable-app", action="store_true", help="Enable the Critic front-end app."
    )
    basic_group.add_argument(
        "--app-file",
        default="/etc/uwsgi/apps-available/critic-backend-%s.ini" % identity,
        help="Target path for app file",
    )
    basic_group.add_argument(
        "--enabled-app-link",
        default="/etc/uwsgi/apps-enabled/critic-backend-%s.ini" % identity,
        help="Target path for symlink to app file that enables the app",
    )

    parser.set_defaults(need_session=True)


def check_uwsgi_python36(uwsgi_executable: str) -> bool:
    try:
        process = subprocess.Popen(
            [
                uwsgi_executable,
                "--need-plugin",
                "python36",
                "--print",
                "uwsgi_python36",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        stdout, _ = process.communicate()
        return stdout == b"uwsgi_python36\n"
    except OSError:
        return False


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
    uwsgi_executable = distutils.spawn.find_executable("uwsgi")
    if not uwsgi_executable:
        if not arguments.install_uwsgi:
            fail(
                "Could not find `uwsgi` executable in $PATH!",
                "Rerun with --install-uwsgi to attempt to install required "
                "packages automatically.",
            )
        install("uwsgi")
        uwsgi_executable = distutils.spawn.find_executable("uwsgi")
        if not uwsgi_executable:
            fail("Still could not find `uwsgi` executable in $PATH!")

    if not check_uwsgi_python36(uwsgi_executable):
        if not arguments.install_uwsgi:
            fail("The `python36` uWSGI plugin is not supported!")
        install("uwsgi-plugin-python3")
        if not check_uwsgi_python36(uwsgi_executable):
            fail("The `python36` uWSGI plugin is still not supported!")

    if os.path.exists(arguments.app_file):
        if arguments.force:
            logger.debug("%s: file already exists; will overwrite", arguments.app_file)
        else:
            fail("%s: file already exists!" % arguments.app_file)
    directory = os.path.dirname(arguments.app_file)
    if not os.path.isdir(directory):
        fail("%s: no such directory!" % directory)
    if arguments.enable_app:
        if os.path.exists(arguments.enabled_app_link):
            if arguments.force:
                logger.debug(
                    "%s: file already exists; will overwrite",
                    arguments.enabled_app_link,
                )
            else:
                fail("%s: file already exists!" % arguments.enabled_app_link)
        directory = os.path.dirname(arguments.enabled_app_link)
        if not os.path.isdir(directory):
            fail("%s: no such directory!" % directory)

    try:
        pwd.getpwnam(arguments.httpd_user)
    except KeyError:
        fail("%s: no such user!" % arguments.httpd_user)
    try:
        grp.getgrnam(arguments.httpd_group)
    except KeyError:
        fail("%s: no such group!" % arguments.httpd_group)

    configuration = base.configuration()

    parameters = {
        "sockets_dir": os.path.join(configuration["paths.runtime"], "sockets"),
        "home_dir": configuration["paths.home"],
        "settings_dir": base.settings_dir(),
        "httpd_username": arguments.httpd_user,
        "httpd_groupname": arguments.httpd_group,
        "critic_username": configuration["system.username"],
        "critic_groupname": configuration["system.groupname"],
        "processes": arguments.processes,
        "threads": arguments.threads,
    }

    app_file_source = (TEMPLATE % parameters).strip()

    with as_root():
        fd, path = tempfile.mkstemp(
            dir=os.path.dirname(os.path.dirname(arguments.app_file))
        )

        with os.fdopen(fd, "w", encoding="utf-8") as app_file:
            print(app_file_source, file=app_file)

        if os.path.isfile(arguments.app_file):
            os.unlink(arguments.app_file)
        os.rename(path, arguments.app_file)
        os.chmod(arguments.app_file, 0o644)

        logger.info("Created app file: %s", arguments.app_file)

        if arguments.enable_app:
            if os.path.isfile(arguments.enabled_app_link):
                os.unlink(arguments.enabled_app_link)
            os.symlink(arguments.app_file, arguments.enabled_app_link)
            logger.info(
                "Enabled app: %s -> %s", arguments.enabled_app_link, arguments.app_file
            )

    if arguments.enable_app:
        service("restart", "uwsgi")

    container = await api.systemsetting.fetch(critic, key="frontend.container")

    async with api.transaction.start(critic) as transaction:
        await transaction.modifySystemSetting(container).setValue("uwsgi")
        await transaction.addSystemEvent(
            "install",
            "container",
            "Installed uWSGI backend app: %s" % arguments.app_file,
            {
                "flavor": "uwsgi",
                "arguments": {
                    "processes": arguments.processes,
                    "threads": arguments.threads,
                    "httpd_user": arguments.httpd_user,
                    "httpd_group": arguments.httpd_group,
                    "app_file": arguments.app_file,
                },
            },
        )

    logger.info("Updated Critic's system settings:")
    logger.info("  frontend.container=%s", json.dumps(container.value))

    return 0
