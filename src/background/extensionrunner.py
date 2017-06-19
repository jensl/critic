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
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import configuration
import textutils
import background.utils
import extensions.execute
import communicate

class ExtensionRunner(background.utils.PeerServer):
    class Extension(background.utils.PeerServer.SpawnedProcess):
        def __init__(self, server, client, process, timeout):
            super(ExtensionRunner.Extension, self).__init__(
                server, process, deadline=time.time() + timeout)
            self.client = client
            self.stdout = self.stderr = None
            self.did_time_out = False

        def handle_input(self, pipe, data):
            assert pipe in (self.process.stdout, self.process.stderr)
            if pipe == self.process.stdout:
                self.stdout = data
            else:
                self.stderr = data

        def timed_out(self):
            super(ExtensionRunner.Extension, self).timed_out()
            self.server.debug("Timeout, killing process [pid=%d]" % self.pid)
            self.did_time_out = True

        def check_result(self):
            self.client.finished(self)

    class Client(background.utils.PeerServer.SocketPeer):
        def __init__(self, server, peersocket):
            super(ExtensionRunner.Client, self).__init__(server, peersocket)

        def handle_input(self, _file, data):
            data = textutils.json_decode(data)

            process = self.server.get_process(data["flavor"])

            extension = ExtensionRunner.Extension(
                self.server, self, process, data["timeout"])
            extension.write(data["stdin"])
            extension.close()

            self.server.add_peer(extension)

        def finished(self, process):
            if process.did_time_out:
                status = status_text = "timeout"
            else:
                status = "ok"
                if process.returncode == 0:
                    status_text = "success"
                else:
                    status_text = "error(%d)" % process.returncode

            self.server.debug("Process finished: %s [pid=%d]"
                              % (status_text, process.pid))

            if process.stdout:
                self.server.debug("  stdout=%r" % process.stdout)
            if process.stderr:
                self.server.debug("  stderr=%r" % process.stderr)

            self.write(textutils.json_encode({
                "status": status,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "returncode": process.returncode
            }))
            self.close()

    def __init__(self):
        service = configuration.services.EXTENSIONRUNNER

        super(ExtensionRunner, self).__init__(service=service)

        self.target_cached_processes = service["cached_processes"]
        self.cached_processes = []

    def run(self):
        if not configuration.extensions.ENABLED:
            self.info("service stopping: extension support not enabled")
            return

        self.__fill_cache()

        super(ExtensionRunner, self).run()

    def handle_peer(self, peersocket, peeraddress):
        return ExtensionRunner.Client(self, peersocket)

    def peer_destroyed(self, peer):
        self.__cache_process()

    def signal_idle_state(self):
        super(ExtensionRunner, self).signal_idle_state()
        self.__fill_cache()

    def get_process(self, flavor):
        if flavor == configuration.extensions.DEFAULT_FLAVOR \
                and self.cached_processes:
            process = self.cached_processes.pop(0)
            self.debug("Using cached process [pid=%d]" % process.pid)
        else:
            process = extensions.execute.startProcess(flavor)
            self.debug("Started new process [pid=%d]" % process.pid)
        return process

    def __fill_cache(self):
        while self.__cache_process():
            pass

    def __cache_process(self):
        if len(self.cached_processes) < self.target_cached_processes:
            process = extensions.execute.startProcess(
                configuration.extensions.DEFAULT_FLAVOR)
            self.debug("Started cached process [pid=%d]" % process.pid)
            self.cached_processes.append(process)
            return True
        else:
            return False

def start_service():
    extensionrunner = ExtensionRunner()
    return extensionrunner.start()

background.utils.call("extensionrunner", start_service)
