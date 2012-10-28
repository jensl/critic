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

import sys
import os
import os.path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

from textutils import json_decode, json_encode

sys_stdout = sys.stdout

if "--slave" in sys.argv[1:]:
    import StringIO
    import traceback

    import index

    data = sys.stdin.read()
    request = json_decode(data)

    def reject(message):
        sys_stdout.write(json_encode({ "status": "reject", "message": message }))
        sys.exit(0)

    def error(message):
        sys_stdout.write(json_encode({ "status": "error", "error": message }))
        sys.exit(0)

    create_branches = []
    delete_branches = []
    update_branches = []

    create_tags = []
    delete_tags = []
    update_tags = []

    user_name = request["user_name"]
    repository_name = request["repository_name"]

    sys.stdout = StringIO.StringIO()

    index.init()

    try:
        try:
            for ref in request["refs"]:
                name = ref["name"]
                old_sha1 = ref["old_sha1"]
                new_sha1 = ref["new_sha1"]

                if "//" in name: reject("invalid ref name: '%s'" % name)
                if not name.startswith("refs/"): reject("unexpected ref name: '%s'" % name)

                name = name[len("refs/"):]

                if name.startswith("heads/"):
                    name = name[len("heads/"):]
                    if new_sha1 == '0000000000000000000000000000000000000000':
                        delete_branches.append(name)
                    elif old_sha1 == '0000000000000000000000000000000000000000':
                        create_branches.append((name, new_sha1))
                    else:
                        update_branches.append((name, old_sha1, new_sha1))
                elif name.startswith("tags/"):
                    name = name[len("tags/"):]
                    if old_sha1 == '0000000000000000000000000000000000000000':
                        create_tags.append((name, new_sha1))
                    elif new_sha1 == '0000000000000000000000000000000000000000':
                        delete_tags.append(name)
                    else:
                        update_tags.append((name, old_sha1, new_sha1))
                elif name.startswith("replays/"):
                    index.processCommits(repository_name, new_sha1)
                elif name.startswith("keepalive/"):
                    name = name[len("keepalive/"):]
                    if name != new_sha1: reject("invalid update of '%s'; value is not %s" % (ref["name"], name))
                    index.processCommits(repository_name, new_sha1)
                elif name.startswith("temporary/"):
                    name = name[len("temporary/"):]
                    if new_sha1 != '0000000000000000000000000000000000000000':
                        index.processCommits(repository_name, new_sha1)
                else:
                    reject("unexpected ref name: '%s'" % ref["name"])

            multiple = (len(delete_branches) + len(update_branches) + len(create_branches) + len(delete_tags) + len(update_tags) + len(create_tags)) > 1
            info = []

            for name in delete_branches:
                index.deleteBranch(repository_name, name)
                info.append("branch deleted: %s" % name)

            for name, old, new in update_branches:
                index.updateBranch(user_name, repository_name, name, old, new, multiple)
                info.append("branch updated: %s (%s..%s)" % (name, old[:8], new[:8]))

            index.createBranches(user_name, repository_name, create_branches)

            for name, new in create_branches:
                info.append("branch created: %s (%s)" % (name, new[:8]))

            for name in delete_tags:
                index.deleteTag(repository_name, name)
                info.append("tag deleted: %s" % name)

            for name, old, new in update_tags:
                index.updateTag(repository_name, name, old, new)
                info.append("tag updated: %s (%s..%s)" % (name, old[:8], new[:8]))

            for name, new in create_tags:
                index.createTag(repository_name, name, new)
                info.append("tag created: %s (%s)" % (name, new[:8]))

            sys_stdout.write(json_encode({ "status": "ok", "accept": True, "output": sys.stdout.getvalue(), "info": info }))

            index.finish()
        except index.IndexException, exception:
            sys_stdout.write(json_encode({ "status": "ok", "accept": False, "output": exception.message, "info": info }))
        except SystemExit:
            raise
        except:
            exception = traceback.format_exc()
            message = """\
%s

Request:
%s

%s""" % (exception.splitlines()[-1], json_encode(request, indent=2), traceback.format_exc())

            sys_stdout.write(json_encode({ "status": "error", "error": message }))
    finally:
        index.abort()
else:
    import configuration

    from background.utils import PeerServer, indent

    class GitHookServer(PeerServer):
        class ChildProcess(PeerServer.ChildProcess):
            def __init__(self, server, client):
                super(GitHookServer.ChildProcess, self).__init__(server, [sys.executable, sys.argv[0], "--slave"])
                self.__client = client

            def handle_input(self, data):
                try: result = json_decode(data)
                except ValueError: result = { "status": "error", "error": "invalid response:\n" + indent(data) }
                if result["status"] == "ok":
                    for item in result["info"]:
                        self.server.info(item)
                    if result["output"]:
                        self.__client.write(result["output"].strip() + "\n")
                    if result["accept"]:
                        self.__client.write("ok\n")
                elif result["status"] == "reject":
                    self.server.warning(result["message"])
                    self.__client.write(result["message"].strip() + "\n")
                else:
                    self.server.error(result["error"])
                    self.__client.write("""\
An exception was raised while processing the request.  A message has
been sent to the system administrator(s).
""")
                self.__client.close()

        class Client(PeerServer.SocketPeer):
            def handle_input(self, data):
                lines = data.splitlines()

                self.__request = { "user_name": lines[0],
                                   "repository_name": lines[1],
                                   "refs": [{ "name": name, "old_sha1": old_sha1, "new_sha1": new_sha1 }
                                            for old_sha1, new_sha1, name in map(str.split, lines[2:])] }

                self.server.info("session started: %s / %s" % (self.__request["user_name"], self.__request["repository_name"]))

                child_process = GitHookServer.ChildProcess(self.server, self)
                child_process.write(json_encode(self.__request))
                child_process.close()
                self.server.add_peer(child_process)

            def destroy(self):
                self.server.info("session ended: %s / %s" % (self.__request["user_name"], self.__request["repository_name"]))

        def __init__(self):
            super(GitHookServer, self).__init__(service=configuration.services.GITHOOK)

            os.chmod(configuration.services.GITHOOK["address"], 0770)

        def handle_peer(self, peersocket, peeraddress):
            return GitHookServer.Client(self, peersocket)

    server = GitHookServer()
    server.run()
