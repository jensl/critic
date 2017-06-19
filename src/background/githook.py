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

import configuration
import background.utils
import dbutils
import auth

from textutils import json_decode, json_encode

try:
    from customization.email import getUserEmailAddress
except ImportError:
    def getUserEmailAddress(_username):
        return None

def getUser(db, user_name):
    if user_name == configuration.base.SYSTEM_USER_NAME:
        return dbutils.User.makeSystem()
    try:
        return dbutils.User.fromName(db, user_name)
    except dbutils.NoSuchUser:
        if configuration.base.AUTHENTICATION_MODE == "host":
            email = getUserEmailAddress(user_name)
            return dbutils.User.create(
                db, user_name, user_name, email, email_verified=None)
        raise

sys_stdout = sys.stdout

def slave():
    import StringIO
    import traceback

    import dbutils
    import gitutils
    import index

    def reject(message):
        sys_stdout.write(json_encode({ "status": "reject", "message": message }))
        sys.exit(0)

    def error(message):
        sys_stdout.write(json_encode({ "status": "error", "error": message }))
        sys.exit(0)

    db = dbutils.Database.forUser()

    try:
        data = sys.stdin.read()
        request = json_decode(data)

        create_branches = []
        delete_branches = []
        update_branches = []

        create_tags = []
        delete_tags = []
        update_tags = []

        user = getUser(db, request["user_name"])
        authentication_labels = auth.DATABASE.getAuthenticationLabels(user)

        db.setUser(user, authentication_labels)

        try:
            repository = gitutils.Repository.fromName(
                db, request["repository_name"], for_modify=True)
        except auth.AccessDenied as error:
            reject(error.message)

        if request["flags"] and user.isSystem():
            flags = dict(flag.split("=", 1) for flag in request["flags"].split(","))
        else:
            flags = {}

        sys.stdout = StringIO.StringIO()

        commits_to_process = set()

        for ref in request["refs"]:
            name = ref["name"]
            old_sha1 = ref["old_sha1"]
            new_sha1 = ref["new_sha1"]

            if "//" in name:
                reject("invalid ref name: '%s'" % name)
            if not name.startswith("refs/"):
                reject("unexpected ref name: '%s'" % name)

            if new_sha1 != '0000000000000000000000000000000000000000':
                commits_to_process.add(new_sha1)

            name = name[len("refs/"):]

            if name.startswith("heads/"):
                name = name[len("heads/"):]
                if new_sha1 == '0000000000000000000000000000000000000000':
                    delete_branches.append((name, old_sha1))
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
            elif name.startswith("temporary/") or name.startswith("keepalive/"):
                # len("temporary/") == len("keepalive/")
                name = name[len("temporary/"):]
                if name != new_sha1:
                    reject("invalid update of '%s'; value is not %s" % (ref["name"], name))
            else:
                reject("unexpected ref name: '%s'" % ref["name"])

        multiple = (len(delete_branches) + len(update_branches) + len(create_branches) + len(delete_tags) + len(update_tags) + len(create_tags)) > 1
        info = []

        for sha1 in commits_to_process:
            index.processCommits(db, repository, sha1)

        for name, old in delete_branches:
            index.deleteBranch(db, user, repository, name, old)
            info.append("branch deleted: %s" % name)

        for name, old, new in update_branches:
            index.updateBranch(db, user, repository, name, old, new, multiple, flags)
            info.append("branch updated: %s (%s..%s)" % (name, old[:8], new[:8]))

        index.createBranches(db, user, repository, create_branches, flags)

        for name, new in create_branches:
            info.append("branch created: %s (%s)" % (name, new[:8]))

        for name in delete_tags:
            index.deleteTag(db, user, repository, name)
            info.append("tag deleted: %s" % name)

        for name, old, new in update_tags:
            index.updateTag(db, user, repository, name, old, new)
            info.append("tag updated: %s (%s..%s)" % (name, old[:8], new[:8]))

        for name, new in create_tags:
            index.createTag(db, user, repository, name, new)
            info.append("tag created: %s (%s)" % (name, new[:8]))

        sys_stdout.write(json_encode({ "status": "ok", "accept": True, "output": sys.stdout.getvalue(), "info": info }))

        db.commit()
    except index.IndexException as exception:
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
        db.close()

class GitHookServer(background.utils.PeerServer):
    class ChildProcess(background.utils.PeerServer.ChildProcess):
        def __init__(self, server, client):
            super(GitHookServer.ChildProcess, self).__init__(server, [sys.executable, sys.argv[0], "--slave"])
            self.__client = client

        def handle_input(self, _file, data):
            try:
                result = json_decode(data)
            except ValueError:
                result = { "status": "error",
                           "error": ("invalid response:\n" +
                                     background.utils.indent(data)) }
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
                if configuration.debug.IS_DEVELOPMENT:
                    self.__client.write("\n" + result["error"].strip() + "\n")
            self.__client.close()

    class Client(background.utils.PeerServer.SocketPeer):
        def handle_input(self, _file, data):
            lines = data.splitlines()

            user_name = lines[0]

            # The second line is the value of the REMOTE_USER environment
            # variable (from the environment with which the git hook ran.)
            #
            # We use it as the actual user only if the actual user was the
            # Critic system user, meaning the push was performed by the
            # branch tracker service, the web front-end (for instance via
            # 'git http-backend') or an extension.
            if user_name == configuration.base.SYSTEM_USER_NAME and lines[1]:
                user_name = lines[1]

            self.__request = { "user_name": user_name,
                               "repository_name": lines[2],
                               "flags": lines[3],
                               "refs": [{ "name": name,
                                          "old_sha1": old_sha1,
                                          "new_sha1": new_sha1 }
                                        for old_sha1, new_sha1, name
                                        in map(str.split, lines[4:])] }

            self.server.info("session started: %s / %s"
                             % (self.__request["user_name"],
                                self.__request["repository_name"]))

            child_process = GitHookServer.ChildProcess(self.server, self)
            child_process.write(json_encode(self.__request))
            child_process.close()
            self.server.add_peer(child_process)

        def destroy(self):
            self.server.info("session ended: %s / %s"
                             % (self.__request["user_name"],
                                self.__request["repository_name"]))

    def __init__(self):
        super(GitHookServer, self).__init__(service=configuration.services.GITHOOK)

    def startup(self):
        super(GitHookServer, self).startup()

        os.chmod(configuration.services.GITHOOK["address"], 0770)

    def handle_peer(self, peersocket, peeraddress):
        return GitHookServer.Client(self, peersocket)

def start_service():
    server = GitHookServer()
    return server.start()

if "--slave" in sys.argv[1:]:
    background.utils.call("githook", slave)
else:
    background.utils.call("githook", start_service)
