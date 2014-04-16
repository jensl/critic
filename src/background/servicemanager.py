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
import subprocess
import time
import signal
import os
import json
import glob

import configuration

# Number of seconds to wait for startup synchronization.
STARTUP_SYNC_TIMEOUT = 30

if "--slave" in sys.argv:
    import background.utils

    class ServiceManager(background.utils.PeerServer):
        # The master process manages our pid file, so tell our base class to
        # leave it alone.
        manage_pidfile = False

        class Service(object):
            class Process(background.utils.PeerServer.ChildProcess):
                def __init__(self, service, input_data):
                    super(ServiceManager.Service.Process, self).__init__(
                        service.manager, [sys.executable, "-m", service.module],
                        stderr=subprocess.STDOUT)

                    self.__service = service
                    self.__output = None
                    if input_data:
                        self.write(json.dumps(input_data))
                    self.close()

                def handle_input(self, data):
                    self.__output = data

                def destroy(self):
                    super(ServiceManager.Service.Process, self).destroy()
                    self.__service.stopped(self.returncode, self.__output)

            def __init__(self, manager, service_data):
                self.manager = manager
                self.name = service_data["name"]
                self.module = service_data["module"]
                self.started = None
                self.process = None
                self.callbacks = []

            def signal_callbacks(self, event):
                self.callbacks = filter(lambda callback: callback(event), self.callbacks)

            def start(self, input_data):
                self.process = ServiceManager.Service.Process(self, input_data)
                self.started = time.time()
                self.manager.add_peer(self.process)
                self.manager.info("%s: started (pid=%d)" % (self.name, self.process.pid))
                self.input_data = input_data
                self.signal_callbacks("started")

            def restart(self, callback=None):
                if callback:
                    self.callbacks.append(callback)
                self.start(self.input_data)

            def stop(self, callback=None):
                if callback:
                    self.callbacks.append(callback)
                if self.process:
                    self.manager.info("%s: sending process SIGTERM" % self.name)
                    self.process.kill(signal.SIGTERM)

            def stopped(self, returncode, output):
                restart = not self.manager.terminated and not self.manager.restart_requested
                if returncode != 0:
                    message = "%s: exited with returncode %d" % (self.name, returncode)
                    if output:
                        message += "\n" + background.utils.indent(output)
                    if time.time() - self.started < 1:
                        message += "\n  Process restarted less than 1 second ago; not restarting."
                        restart = False
                    self.manager.error(message)
                else:
                    self.manager.info("%s: exited normally" % self.name)
                    if not self.callbacks:
                        restart = False
                self.process = None
                if restart:
                    self.restart()
                else:
                    self.signal_callbacks("stopped")

        class Client(background.utils.PeerServer.SocketPeer):
            def __init__(self, manager, peersocket):
                super(ServiceManager.Client, self).__init__(manager, peersocket)
                self.__manager = manager

            def send_response(self, value):
                self.write(background.utils.json_encode(value))
                self.close()

            def handle_input(self, data):
                result = self.send_response

                try:
                    request = background.utils.json_decode(data)
                except:
                    return result({ "status": "error",
                                    "error": "invalid input: JSON decode failed" })

                if type(request) is not dict:
                    return result({ "status": "error",
                                    "error": "invalid input: expected object" })

                if request.get("query") == "status":
                    services = { "manager": { "module": "background.servicemanager",
                                              "uptime": time.time() - self.__manager.started,
                                              "pid": os.getpid() }}

                    for service in self.__manager.services:
                        uptime = time.time() - service.started if service.started else -1
                        pid = service.process.pid if service.process else -1
                        services[service.name] = { "module": service.module,
                                                   "uptime": uptime,
                                                   "pid": pid }

                    return result({ "status": "ok", "services": services })
                elif request.get("command") == "restart":
                    if "service" not in request:
                        return result({ "status": "error",
                                        "error": "invalid input: no service specified" })
                    if request["service"] == "manager":
                        self.__manager.info("restart requested")
                        self.__manager.requestRestart()
                        return result({ "status": "ok" })
                    for service in self.__manager.services:
                        if service.name == request.get("service"):
                            self.__manager.info("%s: restart requested" % service.name)
                            def callback(event):
                                self.send_response({ "status": "ok",
                                                     "event": event })
                            if service.process: service.stop(callback)
                            else: service.restart(callback)
                            break
                    else:
                        return result({ "status": "error", "error": "%s: no such service" % request.get("service") })
                else:
                    return result({ "status": "error", "error": "invalid input: unsupported data" })

        def __init__(self, input_data):
            service = configuration.services.SERVICEMANAGER.copy()

            super(ServiceManager, self).__init__(service=service)

            self.input_data = input_data
            self.services = []
            self.started = time.time()

        def handle_peer(self, peersocket, peeraddress):
            return ServiceManager.Client(self, peersocket)

        def startup(self):
            super(ServiceManager, self).startup()

            for service_data in configuration.services.SERVICEMANAGER["services"]:
                starting_path = service_data["pidfile_path"] + ".starting"
                with open(starting_path, "w") as starting:
                    starting.write("%s\n" % time.ctime())

                service = ServiceManager.Service(self, service_data)
                service.start(self.input_data.get(service.name))
                self.services.append(service)

        def shutdown(self):
            for service in self.services:
                service.stop()

            super(ServiceManager, self).shutdown()

        def requestRestart(self):
            super(ServiceManager, self).requestRestart()

            for service in self.services:
                service.stop()

    def start_service():
        stdin_data = sys.stdin.read()

        if stdin_data:
            input_data = json.loads(stdin_data)
        else:
            input_data = {}

        manager = ServiceManager(input_data)
        return manager.start()

    background.utils.call("servicemanager", start_service)
else:
    import errno
    import pwd
    import grp
    import stat

    pwentry = pwd.getpwnam(configuration.base.SYSTEM_USER_NAME)
    grentry = grp.getgrnam(configuration.base.SYSTEM_GROUP_NAME)

    uid = pwentry.pw_uid
    gid = grentry.gr_gid
    home = pwentry.pw_dir

    import daemon

    pidfile_path = configuration.services.SERVICEMANAGER["pidfile_path"]

    if os.path.isfile(pidfile_path):
        print >>sys.stderr, "%s: file exists; daemon already running?" % pidfile_path
        sys.exit(1)

    pidfile_dir = os.path.dirname(pidfile_path)
    try:
        # /var/run is typically a tmpfs that gets nuked on reboot,
        # so recreate /var/run/critic/IDENTITY if it doesn't exist.
        os.makedirs(pidfile_dir)
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise
    else:
        os.chown(pidfile_dir, uid, gid)
        os.chmod(pidfile_dir, 0750 | stat.S_ISUID | stat.S_ISGID)

    os.environ["HOME"] = home
    os.chdir(home)

    smtp_credentials_path = os.path.join(configuration.paths.CONFIG_DIR,
                                         "configuration",
                                         "smtp-credentials.json")
    if os.path.isfile(smtp_credentials_path):
        with open(smtp_credentials_path) as smtp_credentials_file:
            smtp_credentials = json.load(smtp_credentials_file)
    else:
        smtp_credentials = None

    input_data = { "maildelivery": { "credentials": smtp_credentials }}

    os.setgid(gid)
    os.setuid(uid)

    starting_pattern = os.path.join(os.path.dirname(pidfile_path), "*.starting")

    # Remove any stale/unexpected *.starting files that would otherwise break
    # our startup synchronization.
    for filename in glob.glob(starting_pattern):
        try:
            os.unlink(filename)
        except OSError as error:
            print >>sys.stderr, error

    with open(pidfile_path + ".starting", "w") as starting:
        starting.write("%s\n" % time.ctime())

    def wait_for_startup_sync():
        deadline = time.time() + STARTUP_SYNC_TIMEOUT
        while True:
            filenames = glob.glob(starting_pattern)
            if not filenames:
                return 0
            if time.time() > deadline:
                break
            time.sleep(0.1)
        print >>sys.stderr
        print >>sys.stderr, ("Startup synchronization timeout after %d seconds!"
                             % STARTUP_SYNC_TIMEOUT)
        print >>sys.stderr, "Services still starting:"
        for filename in filenames:
            print >>sys.stderr, "  " + os.path.basename(filename)
        return 1

    with open(pidfile_path, "w") as pidfile:
        daemon.detach(parent_exit_hook=wait_for_startup_sync)
        pidfile.write("%s\n" % os.getpid())

    was_terminated = False

    def terminated(signum, frame):
        global was_terminated
        was_terminated = True

    signal.signal(signal.SIGTERM, terminated)

    while not was_terminated:
        process = subprocess.Popen(
            [sys.executable, "-m", "background.servicemanager", "--slave"],
            stdin=subprocess.PIPE)

        process.stdin.write(json.dumps(input_data))
        process.stdin.close()

        while not was_terminated:
            try:
                pid, status = os.wait()
                if pid == process.pid:
                    process = None
                    break
            except OSError as error:
                if error.errno == errno.EINTR: continue
                else: break

    if process:
        try:
            process.send_signal(signal.SIGTERM)
            process.wait()
        except:
            pass

    try:
        os.unlink(pidfile_path)
    except:
        pass
