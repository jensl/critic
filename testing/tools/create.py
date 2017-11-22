# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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

import sys
import os
import argparse
import multiprocessing
import subprocess
import re

import testing

vm_started = False


def fail(error, *additional):
    testing.logger.error(error)
    for message in additional:
        testing.logger.info(message)
    if vm_started:
        testing.pause()
    sys.exit(1)


def guess_guest_os(cd_image):
    if re.match(r"ubuntu-.*\.iso", cd_image):
        guest_os = "Ubuntu"
    elif re.match(r"debian-.*\.iso", cd_image):
        guest_os = "Debian"
    else:
        fail("Failed to identify guest OS")

    if re.search(r"-i386(?:-.*)?\.iso$", cd_image):
        pass
    elif re.search(r"-amd64(?:-.*)?\.iso$", cd_image):
        guest_os += "_64"
    else:
        fail("Failed to identify guest OS architecture")

    return guest_os


def run_vboxmanage(*arguments):
    try:
        output = subprocess.check_output(["VBoxManage"] + list(arguments))
    except subprocess.CalledProcessError as error:
        fail(
            "Command failed: VBoxManage %s\n%s"
            % (" ".join(arguments), error.output.decode())
        )
    return output.decode()


def list_os_types():
    output = run_vboxmanage("list", "ostypes")
    os_types = set()

    for line in output.splitlines():
        match = re.match("ID:\s+(.*)", line)
        if match:
            os_types.add(match.group(1))

    return os_types


def list_hostonly_ifs():
    output = run_vboxmanage("list", "hostonlyifs")
    hostonly_ifs = {}
    name = None

    for line in output.splitlines():
        match = re.match("Name:\s+(.*)$", line)
        if match:
            name = match.group(1)
            continue
        match = re.match("IPAddress:\s+(.*)$", line)
        if match:
            hostonly_ifs[name] = match.group(1)

    return hostonly_ifs


def list_hosts(hostonly_if_ip):
    network = hostonly_if_ip.rpartition(".")[0]
    hosts = {}

    with open("/etc/hosts") as hosts_file:
        for line in hosts_file.read().splitlines():
            line = line.strip()
            if not line or line[0] == "#":
                continue
            match = re.match(r"(\d+.\d+.\d+.\d+)\s+([^\s]+)$", line)
            if match and match.group(1).startswith(network + "."):
                hosts[match.group(1).rpartition(".")[2]] = match.group(2)

    return hosts


def get_next_ip(hostonly_if_ip):
    hosts = list_hosts(hostonly_if_ip)

    for host in range(2, 255):
        if str(host) not in hosts:
            return f"{hostonly_if_ip.rpartition('.')[0]}.{host}"


def main():
    global vm_started

    # Half the number of CPUs of the host system, but at least one.
    default_cpu_count = max(1, multiprocessing.cpu_count() // 2)

    parser = argparse.ArgumentParser(
        description=(
            "Critic testing framework: " "VirtualBox instance creation utility"
        )
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable DEBUG level logging"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Disable INFO level logging"
    )

    parser.add_argument(
        "--base-dir",
        default=os.path.expanduser("~/.critic"),
        help="Base directory to store data under",
    )
    parser.add_argument(
        "--hostname", help="VirtualBox instance hostname (default: same as IDENTIFIER)"
    )
    parser.add_argument(
        "--guest-os", help="Guest OS type (default: guess based on CD_IMAGE filename)"
    )

    parser.add_argument(
        "--ram-size", type=int, default=4096, help="Amount of RAM, in megabytes"
    )
    parser.add_argument(
        "--vram-size", type=int, default=32, help="Amount of Video RAM, in megabytes"
    )
    parser.add_argument(
        "--cpu-count", type=int, default=default_cpu_count, help="Number of CPUs"
    )
    parser.add_argument(
        "--hdd-size", type=int, default=16384, help="HDD size, in megabytes"
    )

    parser.add_argument(
        "--hostonly-if-use",
        default="vboxnet0",
        metavar="INTERFACE",
        help="Use existing host-only interface [default: vboxnet0]",
    )
    parser.add_argument(
        "--hostonly-if-create",
        metavar="IP_ADDRESS",
        help="Create new host-only interface",
    )

    parser.add_argument("identifier", help="VirtualBox instance identifier")
    parser.add_argument("cd_image", help="CD (or DVD) image to install")

    arguments = parser.parse_args()

    logger = testing.configureLogging(arguments)

    hostname = arguments.hostname or arguments.identifier

    if not os.path.isfile(arguments.cd_image):
        fail("%s: no such file" % arguments.cd_image)

    if arguments.guest_os:
        guest_os = arguments.guest_os
        if guest_os not in list_os_types():
            fail("%s: invalid guest OS type (see `VBoxManage list ostypes`)" % guest_os)
    else:
        guest_os = guess_guest_os(os.path.basename(arguments.cd_image))
        logger.info("Identified guest OS: %s", guest_os)

    if not os.path.isdir(arguments.base_dir):
        os.makedirs(arguments.base_dir)

    def do(*args):
        logger.debug("Running: %s", " ".join(["VBoxManage"] + list(args)))
        return run_vboxmanage(*args)

    if arguments.hostonly_if_create:
        hostonly_if_ip = arguments.hostonly_if_create

        for name, ip in list(list_hostonly_ifs().items()):
            if hostonly_if_ip == ip:
                fail(
                    "%s is assigned to '%s'" % (ip, name),
                    "Maybe you meant to use --hostonly-if-use=%s?" % name,
                )

        output = do("hostonlyif", "create")
        for line in output.splitlines():
            match = re.match("Interface '([^']+)'", line)
            if match:
                hostonly_if = match.group(1)
                break
        else:
            fail("Failed to create hostonly interface")

        do("hostonlyif", "ipconfig", hostonly_if, "--ip", hostonly_if_ip)

        logger.info("Created hostonly interface: %s" % hostonly_if)
    else:
        hostonly_ifs = list_hostonly_ifs()
        hostonly_if = arguments.hostonly_if_use
        if hostonly_if not in hostonly_ifs:
            fail("%s: invalid hostonly interface" % hostonly_if)
        hostonly_if_ip = hostonly_ifs[hostonly_if]

    hdd_filename = os.path.join(
        arguments.base_dir, arguments.identifier, arguments.identifier + ".vdi"
    )

    do("createhd", "--filename", hdd_filename, "--size", str(arguments.hdd_size))

    logger.info("Created VM disk: %s" % hdd_filename)

    do(
        "createvm",
        "--name",
        arguments.identifier,
        "--ostype",
        guest_os,
        "--register",
        "--basefolder",
        arguments.base_dir,
    )

    do(
        "modifyvm",
        arguments.identifier,
        "--memory",
        str(arguments.ram_size),
        "--vram",
        str(arguments.vram_size),
        "--cpus",
        str(arguments.cpu_count),
    )

    do(
        "modifyvm",
        arguments.identifier,
        "--nic1",
        "hostonly",
        "--hostonlyadapter1",
        hostonly_if,
    )

    do(
        "storagectl",
        arguments.identifier,
        "--name",
        "IDE Controller",
        "--add",
        "ide",
        "--controller",
        "PIIX4",
        "--bootable",
        "on",
    )

    do(
        "storageattach",
        arguments.identifier,
        "--storagectl",
        "IDE Controller",
        "--port",
        "0",
        "--device",
        "0",
        "--type",
        "dvddrive",
        "--medium",
        arguments.cd_image,
    )

    do(
        "storagectl",
        arguments.identifier,
        "--name",
        "SATA Controller",
        "--add",
        "sata",
        "--controller",
        "IntelAHCI",
        "--bootable",
        "on",
    )

    do(
        "storageattach",
        arguments.identifier,
        "--storagectl",
        "SATA Controller",
        "--port",
        "0",
        "--device",
        "0",
        "--type",
        "hdd",
        "--medium",
        hdd_filename,
    )

    logger.info("Created VM instance: %s", arguments.identifier)

    guest_ip = get_next_ip(hostonly_if_ip)

    if os.access("/etc/hosts", os.W_OK):
        with open("/etc/hosts", "a") as hosts_file:
            hosts_file.write("%s\t%s\n" % (guest_ip, hostname))

        logger.info("Added '%s' to /etc/hosts" % hostname)
    else:
        logger.warning("No write-access to /etc/hosts")
        logger.info(
            "You should add the line '%s %s' to it manually", guest_ip, hostname
        )

    print(
        f"""\

The VM instance is ready to be started.  You should now complete the
installation of the guest OS (which should start automatically) and
then, with the VM instance still running, return to this script.

 - You should configure the guest OS's network as follows:

     IP:      {guest_ip}
     Netmask: 255.255.255.0
     Gateway: {hostonly_if_ip}
     DNS:     <whatever the host system uses>"""
    )

    testing.pause("Press ENTER to start the VM instance: ")

    do("startvm", arguments.identifier)

    logger.info("Started VM instance: %s" % arguments.identifier)

    print(
        f"""\

Guest OS setup checklist:

 - An SSH server must be installed, and you should be able to SSH to
   it from the host system without being prompted for a password:

     (host)$ ssh-copy-id {hostname}  # will ask for password
     (host)$ ssh {hostname}          # should not ask for password

 - The "sudo" program should be installed, available to your user, and
   you should not be prompted for a password when using it.

     (guest)$ addgroup YOUR_USER sudo  # as root (not needed in Ubuntu)
     (guest)$ sudo visudo              # add "NOPASSWD:" where appropriate

 - The name "host" should resolve to the host system's IP:

     (guest)$ echo "{hostonly_if_ip} host" >> /etc/hosts  # as root"""
    )

    testing.pause("Press ENTER when you have finished setting up the guest OS: ")

    do("snapshot", arguments.identifier, "take", "root", "--pause")

    logger.info("Took VM snapshot: root")

    do("snapshot", arguments.identifier, "take", "clean", "--pause")

    logger.info("Took VM snapshot: clean")

    do("controlvm", arguments.identifier, "poweroff")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
