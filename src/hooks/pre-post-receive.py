#!/usr/bin/env python
# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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
import pwd
import socket
import subprocess
import json
import traceback
import stat

def gitconfig(name):
    try:
        return subprocess.check_output(["git", "config", name]).strip()
    except subprocess.CalledProcessError:
        return None

socket_path = gitconfig("critic.socket")
repository_name = gitconfig("critic.name")

if not socket_path or not repository_name:
    print("""Repository is not configured properly!  Please add

[critic]
\tsocket = <socket path>
\tname = <repository name>

to the repository's configuration file.""")
    sys.exit(1)

server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

try:
    server_socket.connect(socket_path)
except:
    print("Failed to connect to Critic's githook service!")
    sys.exit(1)

data = { "hook": os.path.basename(sys.argv[0]),
         "user_name": pwd.getpwuid(os.getuid()).pw_name,
         "repository_name": repository_name,
         "environ": {},
         "refs": [] }

quarantine_path = os.environ.get("GIT_QUARANTINE_PATH")
if quarantine_path:
    # The quarantine object directory is made inaccessible to group/others by
    # some Git versions (e.g. 2.14.1 on Ubuntu 17.10). This is incompatible with
    # our model of processing the update in a separate process run as another
    # user, so make sure the directory is accessible to the group as well.
    current_mode = stat.S_IMODE(os.stat(quarantine_path).st_mode)
    os.chmod(quarantine_path, current_mode | stat.S_IRWXG)

for key, value in os.environ.items():
    if key in ("REMOTE_USER", "CRITIC_FLAGS") or key.startswith("GIT_"):
        data["environ"][key] = os.environ[key]

for line in sys.stdin:
    old_sha1, new_sha1, ref_name = line.rstrip().split(" ", 2)
    data["refs"].append({ "old_sha1": old_sha1,
                          "new_sha1": new_sha1,
                          "ref_name": ref_name })

try:
    server_socket.sendall(json.dumps(data))
    server_socket.shutdown(socket.SHUT_WR)
except:
    traceback.print_exc()
    print("Failed to send command to Critic!")
    sys.exit(1)

receive_buffer = ""
first = True
accept = False
reject = False

while True:
    try:
        received = server_socket.recv(4096)
    except:
        print("Failed to read result from Critic!")
        sys.exit(1)

    if not received:
        break

    receive_buffer += received

    while "\n" in receive_buffer:
        line, _, receive_buffer = receive_buffer.partition("\n")
        data = json.loads(line)
        if "output" in data:
            if first:
                sys.stdout.write("\n")
                first = False
            sys.stdout.write(data["output"].encode("utf-8"))
            sys.stdout.flush()
        if "accept" in data:
            accept = True
        if "reject" in data:
            reject = True

server_socket.close()

if os.path.basename(sys.argv[0]) == "pre-receive":
    if not (accept or reject):
        # The githook service didn't say whether to accept or reject
        # the update.  We'll reject it.
        print("Invalid response from Critic!")

    sys.exit(0 if accept else 1)
