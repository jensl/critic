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

import errno
import grp
import json
import logging
import os
import pwd
import re
import socket
import subprocess
import sys
import tempfile
import time

logger = logging.getLogger(__name__)

from . import install
from . import install_systemd_service
from . import upgrade
from . import frontend_nginx
from . import frontend_uwsgi
from . import container_uwsgi
from . import container_aiohttp
from . import calibrate_pwhash
from . import download_ui

modules = [
    install,
    install_systemd_service,
    upgrade,
    frontend_nginx,
    frontend_uwsgi,
    container_uwsgi,
    container_aiohttp,
    calibrate_pwhash,
    download_ui,
]

from .. import InvalidUser, as_user, as_root, temporary_cwd

__all__ = ["InvalidUser", "as_user", "as_root", "temporary_cwd"]


class TaskFailed(Exception):
    pass


def fail(message, *additional):
    from critic import textutils

    def for_each_line(fn, string):
        for line in textutils.reflow(string, line_length=70).splitlines():
            fn(line)

    for_each_line(logger.error, f"{message}")

    if additional:
        for string in additional:
            logger.info("")
            for_each_line(logger.info, string)
        logger.info("")

    sys.exit(1)


def identify_os(arguments=None):
    if arguments and getattr(arguments, "os_version", None):
        return arguments.os_version

    if not os.path.isfile("/etc/os-release"):
        fail(
            "The system has no /etc/os-release file!",
            "This file typically identifies the OS (e.g. Linux distribution) "
            "and is required for Critic to correctly identify how to perform "
            "OS dependent tasks such as installing packages or creating UNIX "
            "users and groups.",
            "Hint: the --os-version argument can be used to override this "
            "check and tell Critic explicitly which OS version is running.",
        )

    with open("/etc/os-release") as os_release:
        for line in os_release:
            key, _, value = line.strip().partition("=")
            if key != "NAME":
                continue
            value = value.strip("'\"")
            if value == "Alpine Linux":
                return "alpine"
            if value == "Debian GNU/Linux":
                return "debian"
            if value == "Ubuntu":
                return "ubuntu"
            fail("Unsupported OS: %r (from /etc/os-release)" % value)

    if arguments:
        fail("No NAME variable found in /etc/os-release!")

    return None


def apt_get_install(arguments, *packages):
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"

    with as_root():
        try:
            output = subprocess.check_output(
                ["apt-get", "-qq", "-y", "install"] + list(packages),
                env=env,
                encoding="utf-8",
            )
        except subprocess.CalledProcessError as error:
            logger.error(
                "Failed to install packages: %s: %s", " ".join(packages), error.output
            )
            raise TaskFailed

    for line in output.splitlines():
        match = re.match(r"^Setting up ([^ ]+) \(([^)]+)\) \.\.\.", line)
        if match:
            package_name, version = match.groups()
            logger.info("  %s (%s)", package_name, version)


PACKAGE_INSTALLATION = {
    "debian": (apt_get_install, {}),
    "ubuntu": (apt_get_install, {}),
}


def install(arguments, *packages):
    logger.info("Installing packages: %s", " ".join(packages))

    os_install, package_map = PACKAGE_INSTALLATION[identify_os(arguments)]
    os_install(
        arguments,
        *(package_map.get(package_name, package_name) for package_name in packages),
    )


def service(action, name):
    present, past = {
        "start": ("Starting", "Started"),
        "restart": ("Restarting", "Restarted"),
        "reload": ("Reloading", "Reloaded"),
        "stop": ("Stopping", "Stop"),
    }[action]

    try:
        with as_root():
            subprocess.check_output(["service", name, action], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        logger.warning(
            "%s service failed: %s: %s", present, name, error.output.decode().strip()
        )
    else:
        logger.info("%s service: %s", past, name)


def wait_for_connection(host, port, timeout, *, payload=None):
    deadline = time.time() + (timeout or 0)
    while True:
        try:
            connection = socket.create_connection((host, port), timeout=1)
        except socket.gaierror:
            logger.debug("Connection attempt [%s]: host not found", host)
        except socket.timeout:
            logger.debug("Connection attempt [%s:%d]: timeout", host, port)
        except OSError as error:
            if error.errno != errno.ECONNREFUSED:
                raise
            logger.debug("Connection attempt [%s:%d]: ECONNREFUSED", host, port)
        else:
            if payload:
                connection.sendall(payload)
            connection.close()
            logger.debug("Connection attempt [%s:%d]: OK", host, port)
            return True
        remaining = deadline - time.time()
        if remaining >= 1:
            time.sleep(1)
        else:
            return False


def ensure_dir(
    path, *, uid, gid, mode=0o755, force_attributes=True, sub_directories=[]
):
    update_attributes = force_attributes
    if not os.path.isdir(path):
        ensure_dir(os.path.dirname(path), uid=0, gid=0, force_attributes=False)
        logger.info("Creating directory: %s", path)
        os.mkdir(path)
        update_attributes = True
    if update_attributes:
        os.chmod(path, mode)
        os.chown(path, uid, gid)
    for sub_directory in sub_directories:
        sub_directory = os.path.join(path, sub_directory)
        update_attributes = force_attributes
        if not os.path.isdir(sub_directory):
            os.mkdir(sub_directory)
            update_attributes = True
        if update_attributes:
            os.chmod(sub_directory, mode)
            os.chown(sub_directory, uid, gid)


def adduser_debian(username, groupname, *, force_uid=None, home_dir):
    options = [
        "--quiet",
        "--system",
        "--disabled-login",
        f"--ingroup={groupname}",
        f"--home={home_dir}",
    ]
    if force_uid is not None:
        options.append(f"--uid={force_uid}")
    subprocess.check_output(["adduser", *options, username])


def addgroup_debian(groupname, *, force_gid=None):
    options = ["--quiet", "--system"]
    if force_gid is not None:
        options.append(f"--gid={force_gid}")
    subprocess.check_output(["addgroup", *options, groupname])


def adduser_alpine(username, groupname, *, force_uid=None, home_dir):
    options = ["-S", "-D", "-G", groupname, "-h", home_dir]
    if force_uid is not None:
        options.extend(["-u", str(force_uid)])
    subprocess.check_output(["adduser", *options, username])


def addgroup_alpine(groupname, *, force_gid=None):
    options = ["-S"]
    if force_gid is not None:
        options.extend(["-g", str(force_gid)])
    subprocess.check_output(["addgroup", *options, groupname])


USER_GROUP_CREATION = {
    "debian": (adduser_debian, addgroup_debian),
    "ubuntu": (adduser_debian, addgroup_debian),
    "alpine": (adduser_alpine, addgroup_alpine),
}


def ensure_system_user_and_group(
    arguments, *, username, force_uid=None, groupname, force_gid=None, home_dir
):
    adduser, addgroup = USER_GROUP_CREATION[identify_os(arguments)]

    try:
        system_gid = grp.getgrnam(groupname).gr_gid
    except KeyError:
        logger.info("Creating system group: %s", groupname)
        addgroup(groupname, force_gid=force_gid)
        system_gid = grp.getgrnam(groupname).gr_gid

    try:
        system_uid = pwd.getpwnam(username).pw_uid
    except KeyError:
        logger.info("Creating system user: %s", username)
        adduser(username, groupname, force_uid=force_uid, home_dir=home_dir)
        system_uid = pwd.getpwnam(username).pw_uid

    return system_uid, system_gid


def write_configuration(configuration):
    from critic import base

    configuration_path = os.path.join(base.settings_dir(), "configuration.json")

    action = "Created"

    if os.path.isfile(configuration_path):
        with open(configuration_path, encoding="utf-8") as configuration_file:
            try:
                existing = json.load(configuration_file)
            except json.JSONDecodeError:
                logger.warning(
                    "%s: file exists but is not valid JSON!", configuration_path
                )
            else:
                if existing == configuration:
                    logger.debug(
                        "%s: file exists and is up-to-date", configuration_path
                    )
                    return

        action = "Updated"

    with open(configuration_path, "w", encoding="utf-8") as configuration_file:
        json.dump(configuration, configuration_file)

    logger.info("%s file: %s", action, configuration_path)


def setup_filesystem_locations(parser):
    from .. import is_virtualenv, is_quickstarted

    def default_home_dir():
        if "CRITIC_HOME" in os.environ:
            return os.environ["CRITIC_HOME"]
        if is_virtualenv:
            return sys.prefix
        return "/var/lib/critic"

    def default_runtime_dir():
        # Only use |sys.prefix| if quick-started; otherwise /var/run is a good
        # choice even if installed in a virtual environment, since it's often a
        # tmpfs, and files we create there are per-session.
        if is_quickstarted:
            return os.path.join(default_home_dir(), "run")
        return os.path.join("/var/run/critic")

    def default_logs_dir():
        # Only use |sys.prefix| if quick-started; otherwise /var/log is a good
        # choice, since that's where someone would be expecting to find logs.
        if is_quickstarted:
            return os.path.join(default_home_dir(), "log")
        return "/var/log/critic"

    def default_repositories_dir():
        if is_quickstarted:
            return os.path.join(default_home_dir(), "git")
        return "/var/git"

    def default_data_dir():
        return os.path.join(default_home_dir(), "data")

    def default_scratch_dir():
        if is_quickstarted:
            return os.path.join(default_home_dir(), "tmp")
        return tempfile.gettempdir()

    paths_group = parser.add_argument_group("Filesystem locations")
    paths_group.add_argument(
        "--home-dir",
        default=default_home_dir(),
        help="Main directory where persistent files are installed.",
    )
    paths_group.add_argument(
        "--runtime-dir",
        default=default_runtime_dir(),
        help=(
            "Directory in which runtime files (PID files and UNIX sockets) "
            "are created."
        ),
    )
    paths_group.add_argument(
        "--logs-dir",
        default=default_logs_dir(),
        help="Directory in which log files are created.",
    )
    paths_group.add_argument(
        "--repositories-dir",
        default=default_repositories_dir(),
        help="Directory in which Git repositories are stored.",
    )
    paths_group.add_argument(
        "--data-dir",
        default=default_data_dir(),
        help="Directory in which Critic stores persistent data.",
    )
    paths_group.add_argument(
        "--scratch-dir",
        default=default_scratch_dir(),
        help=(
            "Directory in which Critic stores temporary data that need not persist "
            "across system restarts."
        ),
    )


def setup_database_backup(parser):
    backup_group = parser.add_argument_group("Backup options")
    dump_database_group = backup_group.add_mutually_exclusive_group()
    dump_database_group.add_argument(
        "--dump-database",
        action="store_const",
        const=True,
        dest="dump_database",
        help="Take a database snapshot before upgrading.",
    )
    dump_database_group.add_argument(
        "--no-dump-database",
        action="store_const",
        const=False,
        dest="dump_database",
        help="Do NOT take a database snapshot before upgrading.",
    )
    backup_group.add_argument(
        "--dump-database-file",
        default=time.strftime("criticdb-%Y%m%dT%H%M.dump", time.localtime()),
        help="Name of file to store database dump in.",
    )
