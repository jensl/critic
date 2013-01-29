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
import os
import os.path
import logging
import logging.handlers
import atexit
import socket
import errno
import select
import traceback
import signal
import fcntl
import time

from textutils import json_encode, json_decode, indent

def freeze(d):
    return tuple(sorted(d.items()))
def thaw(f):
    return dict(f)

class AdministratorMailHandler(logging.Handler):
    def __init__(self, logfile_path):
        super(AdministratorMailHandler, self).__init__()
        self.__logfile_name = os.path.basename(logfile_path)

    def emit(self, record):
        import mailutils
        mailutils.sendAdministratorMessage(self.__logfile_name, record.message.splitlines()[0], self.formatter.format(record))

class BackgroundProcess(object):
    def __init__(self, service):
        try: loglevel = getattr(logging, service["loglevel"].upper())
        except: loglevel = logging.INFO

        formatter = logging.Formatter("%(asctime)s - %(levelname)5s - %(message)s")

        file_handler = logging.handlers.RotatingFileHandler(service["logfile_path"], maxBytes=1024**2, backupCount=5)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(loglevel)

        mail_handler = AdministratorMailHandler(service["logfile_path"])
        mail_handler.setFormatter(formatter)
        mail_handler.setLevel(logging.WARNING)

        logger = logging.getLogger()
        logger.setLevel(loglevel)
        logger.addHandler(file_handler)
        logger.addHandler(mail_handler)

        self.terminated = False
        self.interrupted = False
        self.restart_requested = False

        self.__maintenance_hooks = []
        self.__logger = logger
        self.__pidfile_path = service.get("pidfile_path")
        self.__create_pidfile()

        signal.signal(signal.SIGHUP, self.__handle_SIGHUP)
        signal.signal(signal.SIGTERM, self.__handle_SIGTERM)

        self.info("service started")

        atexit.register(self.__stopped)

    def __handle_SIGHUP(self, signum, frame):
        self.interrupted = True
    def __handle_SIGTERM(self, signum, frame):
        self.terminated = True

    def __create_pidfile(self):
        if self.__pidfile_path:
            try: os.makedirs(os.path.dirname(self.__pidfile_path))
            except OSError, error:
                if error.errno == errno.EEXIST: pass
                else: raise
            pidfile = open(self.__pidfile_path, "w")
            pidfile.write(str(os.getpid()) + "\n")
            pidfile.close()

    def __delete_pidfile(self):
        if self.__pidfile_path:
            try: os.unlink(self.__pidfile_path)
            except: pass

    def __stopped(self):
        self.info("service stopped")
        self.__delete_pidfile()

    def error(self, message):
        self.__logger.error(message)

    def warning(self, message):
        self.__logger.warning(message)

    def info(self, message):
        self.__logger.info(message)

    def debug(self, message):
        self.__logger.debug(message)

    def exception(self, message="uncaught exception:"):
        self.__logger.error(message + "\n" + indent(traceback.format_exc()))

    def register_maintenance(self, hour, minute, callback):
        now = time.localtime()
        since_last = (now[3] * 3600 + now[4] * 60) - (hour * 3600 + minute * 60)
        if since_last < 0: since_last += 86400
        self.__maintenance_hooks.append([hour, minute, callback, time.time() - since_last])

    def run_maintenance(self):
        if self.__maintenance_hooks:
            now = time.localtime()
            timeout = 86400

            for hook in self.__maintenance_hooks:
                hour, minute, callback, last = hook
                since_last = time.time() - last

                if hour is None:
                    if since_last > 59 * 60 and now[4] >= minute:
                        self.debug("performing hourly maintenance task")
                        callback()
                        hook[3] = time.time()
                    else:
                        timeout = min(timeout, max(3600 - since_last - 60, 1))
                else:
                    if since_last > 23 * 60 * 60 and now[3] >= hour and now[4] >= minute:
                        self.debug("performing daily maintenance task")
                        callback()
                        hook[3] = time.time()
                    else:
                        timeout = min(timeout, max(86400 - since_last - 3600, 60))

            return timeout

    def requestRestart(self):
        self.restart_requested = True

class PeerServer(BackgroundProcess):
    class Peer(object):
        def __init__(self, server, writing, reading):
            self.server = server

            self.__writing = writing
            self.__write_data = ""
            self.__write_closed = False

            if writing:
                fcntl.fcntl(writing, fcntl.F_SETFL, fcntl.fcntl(writing, fcntl.F_GETFL) | os.O_NONBLOCK)

            self.__reading = reading
            self.__read_data = ""
            self.__read_closed = False

            if reading and reading.fileno() != writing.fileno():
                fcntl.fcntl(reading, fcntl.F_SETFL, fcntl.fcntl(reading, fcntl.F_GETFL) | os.O_NONBLOCK)

        def is_finished(self):
            return not self.__writing and not self.__reading

        def writing(self):
            if self.__write_data or self.__write_closed: return self.__writing
            else: return None

        def write(self, data):
            assert self.__writing
            assert not self.__write_closed
            self.__write_data += data

        def close(self):
            assert self.__writing
            assert not self.__write_closed
            self.__write_closed = True

        def do_write(self):
            while self.__write_data:
                nwritten = os.write(self.__writing.fileno(), self.__write_data)
                self.__write_data = self.__write_data[nwritten:]
            if self.__write_closed:
                self.writing_done(self.__writing)
                self.__writing = None

        def reading(self):
            if not self.__read_closed: return self.__reading
            else: return None

        def read(self):
            if self.__read_closed: return self.__read_data
            else: return None

        def do_read(self):
            while True:
                read = os.read(self.__reading.fileno(), 4096)
                if not read:
                    self.reading_done(self.__reading)
                    self.__reading = None
                    self.__read_closed = True
                    self.handle_input(self.__read_data)
                    break
                self.__read_data += read

        def writing_done(self, writing):
            writing.close()

        def reading_done(self, reading):
            reading.close()

        def destroy(self):
            pass

    class SocketPeer(Peer):
        def __init__(self, server, clientsocket):
            super(PeerServer.SocketPeer, self).__init__(server, clientsocket, clientsocket)

        def reading_done(self, reading):
            reading.shutdown(socket.SHUT_RD)

        def writing_done(self, writing):
            writing.shutdown(socket.SHUT_WR)

        def handle_input(self, data):
            pass

    class ChildProcess(Peer):
        def __init__(self, server, args, **kwargs):
            self.__process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, **kwargs)
            self.pid = self.__process.pid
            super(PeerServer.ChildProcess, self).__init__(server, self.__process.stdin, self.__process.stdout)
            self.server.debug("spawned child process (pid=%d)" % self.__process.pid)

        def kill(self, signal):
            self.__process.send_signal(signal)

        def destroy(self):
            self.__process.wait()
            self.returncode = self.__process.returncode
            if self.returncode:
                self.server.error("child process exited (pid=%d, returncode=%d)" % (self.pid, self.returncode))
            else:
                self.server.debug("child process exited (pid=%d, returncode=0)" % self.pid)

    def __init__(self, service):
        super(PeerServer, self).__init__(service)

        self.__peers = []
        self.__address = service.get("address")
        self.__create_listening_socket()

    def __create_listening_socket(self):
        if type(self.__address) == str:
            try: os.makedirs(os.path.dirname(self.__address))
            except OSError, error:
                if error.errno == errno.EEXIST: pass
                else: raise

            if os.path.exists(self.__address):
                connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    connection.connect(self.__address)
                    connection.close()

                    print >>sys.stderr, "ERROR: Server already started!"
                    sys.exit(1)
                except socket.error, error:
                    if error[0] == errno.ECONNREFUSED:
                        self.debug("removing stale socket")
                        os.unlink(self.__address)
                    else: raise

            self.__listening_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.__listening_socket.setblocking(0)
            self.__listening_socket.bind(self.__address)
            self.__listening_socket.listen(4)

            os.chmod(self.__address, 0700)

            self.debug("listening: %s" % self.__address)
        elif type(self.__address) == tuple:
            host, port = self.__address

            self.__listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__listening_socket.setblocking(0)
            self.__listening_socket.bind((host, port))
            self.__listening_socket.listen(4)

            self.debug("listening: %s:%d" % (host, port))
        elif self.__address is None:
            self.__listening_socket = open("/dev/null", "r")

            self.debug("not listening")
        else:
            raise Exception, "invalid address: %r" % self.__address

        atexit.register(self.__destroy_listening_socket)

    def __destroy_listening_socket(self):
        try: self.__listening_socket.close()
        except: pass

        if type(self.__address) == str:
            try: os.unlink(self.__address)
            except: pass

    def run(self):
        try:
            try:
                self.startup()

                while not self.terminated:
                    self.interrupted = False

                    if self.restart_requested:
                        if not self.__peers: break
                        else: self.debug("restart delayed; have %d peers" % len(self.__peers))

                    poll = select.poll()
                    poll.register(self.__listening_socket, select.POLLIN)

                    for peer in self.__peers:
                        if peer.writing(): poll.register(peer.writing(), select.POLLOUT)
                        if peer.reading(): poll.register(peer.reading(), select.POLLIN)

                    def fileno(file):
                        if file: return file.fileno()
                        else: return None

                    while not self.terminated:
                        timeout = self.run_maintenance()

                        if not (timeout is None or self.__peers):
                            self.debug("next maintenance task check scheduled in %d seconds" % timeout)

                        try:
                            events = poll.poll(timeout * 1000 if timeout else None)
                            break
                        except select.error, error:
                            if error[0] == errno.EINTR: continue
                            else: raise

                    if self.terminated: break

                    def catch_error(fn):
                        try: fn()
                        except socket.error, error:
                            if error[0] not in (errno.EAGAIN, errno.EINTR): raise
                        except OSError, error:
                            if error.errno not in (errno.EAGAIN, errno.EINTR): raise

                    for fd, event in events:
                        if fd == self.__listening_socket.fileno():
                            peersocket, peeraddress = self.__listening_socket.accept()
                            peer = self.handle_peer(peersocket, peeraddress)
                            if peer: self.__peers.append(peer)
                            else:
                                try: peersocket.close()
                                except: pass
                        else:
                            for peer in self.__peers[:]:
                                if fd == fileno(peer.writing()) and event != select.POLLIN:
                                    catch_error(peer.do_write)
                                if fd == fileno(peer.reading()) and event != select.POLLOUT:
                                    catch_error(peer.do_read)
                                if peer.is_finished():
                                    peer.destroy()
                                    self.peer_destroyed(peer)
                                    self.__peers.remove(peer)
            except:
                self.exception()
                self.error("service crashed!")
                sys.exit(1)
            else:
                self.info("service shutting down ...")
        finally:
            try: self.shutdown()
            except: self.exception()

            for peer in self.__peers:
                try: peer.destroy()
                except: self.exception()
                try: self.peer_destroyed(peer)
                except: self.exception()

    def add_peer(self, peer):
        self.__peers.append(peer)

    def handle_peer(self, peersocket, peeraddress):
        pass

    def peer_destroyed(self, peer):
        pass

    def startup(self):
        pass
    def shutdown(self):
        pass

class SlaveProcessServer(PeerServer):
    class SlaveChildProcess(PeerServer.ChildProcess):
        def __init__(self, server, client):
            super(SlaveProcessServer.SlaveChildProcess, self).__init__(server, [sys.executable, sys.argv[0], "--slave"])
            self.__client = client

        def handle_input(self, value):
            self.__client.write(value)
            self.__client.close()

    class SlaveClient(PeerServer.SocketPeer):
        def __init__(self, server, peersocket):
            super(SlaveProcessServer.SlaveClient, self).__init__(server, peersocket)

        def handle_input(self, value):
            if value:
                child_process = SlaveProcessServer.SlaveChildProcess(self.server, self)
                child_process.write(value)
                child_process.close()
                self.server.add_peer(child_process)

    def handle_peer(self, peersocket, peeraddress):
        return SlaveProcessServer.SlaveClient(self, peersocket)

class JSONJobServer(PeerServer):
    class Job(PeerServer.ChildProcess):
        def __init__(self, server, client, request):
            super(JSONJobServer.Job, self).__init__(server, [sys.executable, sys.argv[0], "--json-job"], stderr=subprocess.STDOUT)
            self.clients = [client]
            self.request = request
            self.write(json_encode(request))
            self.close()

        def handle_input(self, value):
            try: result = json_decode(value)
            except ValueError:
                self.server.error("invalid response:\n" + indent(value))
                result = self.request.copy()
                result["error"] = value
            for client in self.clients: client.add_result(result)
            self.server.request_finished(self, self.request, result)

    class JobClient(PeerServer.SocketPeer):
        def handle_input(self, value):
            decoded = json_decode(value)
            if isinstance(decoded, list):
                self.__requests = decoded
                self.__pending_requests = map(freeze, decoded)
                self.__results = []
                self.server.add_requests(self)
            else:
                assert isinstance(decoded, dict)
                self.server.execute_command(self, decoded)

        def has_requests(self):
            return bool(self.__pending_requests)

        def get_request(self):
            return self.__pending_requests.pop()

        def add_result(self, result):
            self.__results.append(result)
            if len(self.__results) == len(self.__requests):
                self.write(json_encode(self.__results))
                self.close()

    def __init__(self, service):
        super(JSONJobServer, self).__init__(service)
        self.__clients_with_requests = []
        self.__started_requests = {}
        self.__max_jobs = service.get("max_jobs", 4)

    def __startJobs(self):
        # Repeat "start a job" while there are jobs to start and we haven't
        # reached the limit on number of concurrent jobs to run.
        while self.__clients_with_requests and len(self.__started_requests) < self.__max_jobs:
            # Fetch next request from first client in list of clients with
            # pending requests.
            client = self.__clients_with_requests.pop(0)
            frozen = client.get_request()

            if client.has_requests():
                # Client has more pending requests, so put it back at the end of
                # the list of clients with pending requests.
                self.__clients_with_requests.append(client)

            if frozen in self.__started_requests:
                # Another client has requested the same thing, piggy-back on
                # that job instead of starting another.
                self.__started_requests[frozen].clients.append(client)
                continue

            request = thaw(frozen)

            # Check if this request is already finished.  Default implementation
            # of this callback always returns None.
            result = self.request_result(request)

            if result:
                # Request is already finished; don't bother starting a child
                # process, just report result directly to the client.
                client.add_result(result)
            else:
                # Start child process.
                job = JSONJobServer.Job(self, client, request)
                self.add_peer(job)
                self.request_started(job, request)

    def add_requests(self, client):
        assert client.has_requests()
        self.__clients_with_requests.append(client)
        self.__startJobs()

    def execute_command(self, client, command):
        client.write(json_encode({ "status": "error", "error": "command not supported" }))
        client.close()

    def handle_peer(self, peersocket, peeraddress):
        return JSONJobServer.JobClient(self, peersocket)

    def peer_destroyed(self, peer):
        if isinstance(peer, JSONJobServer.Job): self.__startJobs()

    def request_result(self, request):
        pass
    def request_started(self, job, request):
        self.__started_requests[freeze(request)] = job
    def request_finished(self, job, request, result):
        del self.__started_requests[freeze(request)]
