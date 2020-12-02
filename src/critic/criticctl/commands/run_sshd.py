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
import asyncio
import distutils.spawn
import grp
import logging
import os
import pwd
from pwd import struct_passwd
import signal
import subprocess
import sys
import tempfile
from typing import Optional, Protocol

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from ..utils import as_root
from ..tasks.utils import fail, ensure_dir, ensure_system_user_and_group, identify_os

name = "run-sshd"
title = "Start Critic SSH access"
long_description = """

This command runs an OpenSSH daemon that enables Git repository access over SSH.

Users can only authenticate as a single account (typically named "critic") using
SSH public keys they have registered with Critic via the web front-end.

"""


class Arguments(Protocol):
    loglevel: int
    configuration: base.Configuration

    account_name: str
    listen_host: Optional[str]
    listen_port: int

    host_key_types: str
    host_key_dir: Optional[str]
    host_key_aws_parameter_path: Optional[str]

    sshd: str
    ssh_keygen: str


def generate_host_key(arguments: Arguments, key_type: str, key_file: str) -> None:
    if arguments.ssh_keygen is None:
        fail(
            "No 'ssh-keygen' executable found!",
            "Make sure the OpenSSH utilities are installed and available via "
            "the current search path.",
        )

    logger.info("Generating %s host key: %s", key_type, key_file)
    subprocess.check_call(
        ["ssh-keygen", "-q", "-N", "", "-t", key_type, "-f", key_file]
    )


def key_filename(key_type: str) -> str:
    return f"ssh_host_{key_type}_key"


# _aws_ssm = None


# def aws_ssm(arguments: Arguments) -> int:
#     global _aws_ssm

#     try:
#         import boto3
#     except ImportError:
#         if sys.prefix == sys.base_prefix:
#             pip = "pip3"
#         else:
#             pip = os.path.join(os.path.dirname(sys.argv[0]), "pip")
#         fail(
#             "Failed to import 'boto3' package!",
#             "It can be installed by running this command:",
#             f"  {pip} install boto3",
#         )

#     if arguments.loglevel > logging.DEBUG:
#         botocore_level = logging.WARNING
#     else:
#         botocore_level = logging.INFO
#     logging.getLogger("botocore").setLevel(botocore_level)

#     if _aws_ssm is None:
#         _aws_ssm = boto3.client("ssm")
#     return _aws_ssm


# def aws_parameter_name(arguments: Arguments, key_type: str) -> str:
#     parameter_name = f"{arguments.host_key_aws_parameter_path}/{key_type}"
#     if not parameter_name.startswith("/"):
#         parameter_name = f"/{parameter_name}"
#     return parameter_name


# class NoSuchKey(Exception):
#     pass


# def aws_fetch_host_key(arguments: Arguments, key_type: str) -> str:
#     ssm = aws_ssm(arguments)

#     import botocore.exceptions

#     try:
#         response = ssm.get_parameter(
#             Name=aws_parameter_name(arguments, key_type), WithDecryption=True
#         )
#     except botocore.exceptions.ClientError as error:
#         if error.response["Error"]["Code"] == "ParameterNotFound":
#             raise NoSuchKey()
#         raise

#     logger.debug("response: %r", response)

#     fd, key_file = tempfile.mkstemp(prefix=f"{key_filename(key_type)}.")
#     with open(fd, "w") as file:
#         file.write(response["Parameter"]["Value"])

#     return key_file


# def aws_store_host_key(arguments: Arguments, key_type):
#     ssm = aws_ssm(arguments)

#     key_file = os.path.join(tempfile.mkdtemp(), key_filename(key_type))
#     generate_host_key(arguments, key_type, key_file)

#     with open(key_file, "r") as file:
#         ssm.put_parameter(
#             Name=aws_parameter_name(arguments, key_type),
#             Value=file.read(),
#             Type="SecureString",
#         )

#     return key_file


def ensure_host_key(arguments: Arguments, key_type: str) -> str:
    if arguments.host_key_dir:
        configuration = base.configuration()

        system_uid = pwd.getpwnam(configuration["system.username"]).pw_uid
        system_gid = grp.getgrnam(configuration["system.groupname"]).gr_gid

        ensure_dir(
            arguments.host_key_dir,
            uid=system_uid,
            gid=system_gid,
            mode=0o700,
            force_attributes=False,
        )

        key_file = os.path.join(arguments.host_key_dir, key_filename(key_type))

        if os.path.isfile(key_file):
            logger.debug("%s host key already exists: %s", key_type, key_file)
            return key_file

        generate_host_key(arguments, key_type, key_file)
    # elif arguments.host_key_aws_parameter_path:
    #     try:
    #         key_file = aws_fetch_host_key(arguments, key_type)
    #     except NoSuchKey:
    #         key_file = aws_store_host_key(arguments, key_type)
    else:
        # Fall back to the host key that was created in the image, when the
        # openssh-server package was installed. This is not ideal, obviously.
        key_file = f"/etc/ssh/ssh_host_{key_type}_key"

    return key_file


def setup(parser: argparse.ArgumentParser) -> None:
    configuration = parser.get_default("configuration")

    parser.add_argument(
        "--account-name",
        default=configuration["system.username"],
        help="UNIX account name to allow. (Note: shell access is not allowed.)",
    )
    parser.add_argument(
        "--listen-host", help="Listen address. By default, listen on all interfaces."
    )
    parser.add_argument("--listen-port", type=int, default=22, help="Listen port.")

    parser.add_argument_group("Host key management")
    parser.add_argument(
        "--host-key-types",
        metavar="TYPE,TYPE,...",
        default="rsa,dsa,ecdsa,ed25519",
        help="Comma-separated list of host key types to use",
    )
    parser.add_argument(
        "--host-key-dir",
        metavar="DIR",
        help="Path to directory containing a host (private) key files",
    )
    parser.add_argument(
        "--host-key-aws-parameter-path",
        metavar="PATH",
        help=(
            "Path prefix for AWS Systems Manager Parameter Store parameters "
            "used to store individual host keys"
        ),
    )

    parser.add_argument_group("Executables")

    sshd = distutils.spawn.find_executable("sshd")
    ssh_keygen = distutils.spawn.find_executable("ssh-keygen")

    parser.add_argument(
        "--with-sshd",
        dest="sshd",
        metavar="SSHD",
        default=sshd,
        help="Path to 'sshd' (OpenSSH daemon)",
    )
    parser.add_argument(
        "--with-ssh-keygen",
        dest="ssh_keygen",
        metavar="SSH_KEYGEN",
        default=ssh_keygen,
        help="Path to 'ssh-keygen' (key generation utility)",
    )

    parser.set_defaults(run_as_root=True)

    # enablding password authentication.


def ensure_account(arguments: Arguments, account_pwd: struct_passwd) -> None:
    def account_status():
        logger.debug("running 'passwd -S %s'", arguments.account_name)
        output = subprocess.check_output(
            ["passwd", "-S", arguments.account_name], encoding="utf-8"
        )

        logger.debug("'passwd -S %s => %s", arguments.account_name, output.strip())

        status = output.split()[1]
        assert status in ("L", "NP", "P"), repr(output)
        return status

    def unlock_account():
        logger.debug("running 'passwd -u %s'", arguments.account_name)
        try:
            subprocess.check_output(["passwd", "-u", arguments.account_name])
        except subprocess.CalledProcessError:
            # This will typically fail because no password is set, in which case
            # simply unlocking the account would leave it in a bad state.
            return False
        return account_status() == "P"

    def reset_account_password():
        # Set an (invalid) encrypted password to unlock:str the account:str withou->Nonet
        logger.debug("running 'usermod -p * %s'", arguments.account_name)
        subprocess.check_output(["usermod", "-p", "*", arguments.account_name])

    def reset_account_shell():
        # Set a valid shell. This is required even though we use ForceCommand to
        # restrict access, the forced command is run using the account's shell.
        logger.debug("running 'usermod -s /bin/sh %s'", arguments.account_name)
        subprocess.check_output(["usermod", "-s", "/bin/sh", arguments.account_name])

    with as_root():
        if account_status() == "L":
            logger.info("Unlocking account: %s", arguments.account_name)

            # Try to unlock the account by restoring the previous password.
            if not unlock_account():
                reset_account_password()

        if os.path.basename(account_pwd.pw_shell) in ("false", "nologin"):
            reset_account_shell()


async def main(critic: api.critic.Critic, arguments: Arguments) -> int:
    ensure_system_user_and_group(
        arguments,
        username=arguments.account_name,
        groupname=arguments.configuration["system.groupname"],
        home_dir=tempfile.gettempdir(),
    )

    account_pwd = pwd.getpwnam(arguments.account_name)
    account_uid = account_pwd.pw_uid

    # The commands used to ensure the specified account is suitably set up do
    # not work with BusyBox, installed in Alpine Linux. Instead, we just assume
    # the account is properly set up already.
    if identify_os(arguments) != "alpine":
        ensure_account(arguments, account_pwd)

    host_key_types = arguments.host_key_types.split(",")
    host_key_files = []

    for key_type in host_key_types:
        host_key_files.append(ensure_host_key(arguments, key_type))
        logger.debug("%s: %s", key_type, host_key_files[-1])

    with as_root():
        if not os.path.isdir("/run/sshd"):
            os.mkdir("/run/sshd", mode=0o700)
        else:
            os.chmod("/run/sshd", mode=0o700)

    work_dir = tempfile.mkdtemp()
    os.chown(work_dir, uid=account_uid, gid=-1)

    fd, config_file = tempfile.mkstemp(prefix="sshd_config.", dir=work_dir)
    with open(fd, "w") as file:
        print(f"AllowUsers={arguments.account_name}", file=file)
        print(f"AuthenticationMethods=publickey", file=file)
        print(
            "AuthorizedKeysCommand=/lookup-ssh-key.sh "
            f"{arguments.account_name} %u %t %k",
            file=file,
        )
        print(
            f"AuthorizedKeysCommandUser=" + arguments.configuration["system.username"],
            file=file,
        )
        print("ChallengeResponseAuthentication=no", file=file)
        print("DisableForwarding=yes", file=file)
        print(f"ForceCommand={sys.argv[0]} sshd-client", file=file)

        for key_file in host_key_files:
            print(f"HostKey={key_file}", file=file)

        if arguments.loglevel == logging.DEBUG:
            print("LogLevel=DEBUG", file=file)

        print("PasswordAuthentication=no", file=file)
        print("PermitTTY=no", file=file)
        print("PermitTunnel=no", file=file)
        print("PermitUserEnvironment=yes", file=file)
        print("StrictModes=no", file=file)

    sshd = await asyncio.create_subprocess_exec(
        arguments.sshd, "-D", "-e", "-f", config_file
    )

    logger.debug("sshd process started: %r", sshd.pid)

    stopped = asyncio.Event()

    def stop():
        stopped.set()

    critic.loop.add_signal_handler(signal.SIGINT, stop)
    critic.loop.add_signal_handler(signal.SIGTERM, stop)

    async def wait_for_sshd():
        returncode = await sshd.wait()
        logger.debug("sshd process stopped: %r", returncode)
        return returncode

    sshd_future = asyncio.ensure_future(wait_for_sshd())

    await stopped.wait()

    if sshd.returncode is None:
        sshd.terminate()

    return await sshd_future
