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

from operation import Operation, OperationResult, Optional, OperationError, OperationFailure

import configuration
import textutils

import os
import socket
import signal

class RestartService(Operation):
    def __init__(self):
        Operation.__init__(self, { "service_name": str })

    def process(self, db, user, service_name):
        if not user.hasRole(db, "administrator"):
            raise OperationFailure(code="notallowed", title="Not allowed!", message="Only a system administrator can restart services.")

        if service_name == "wsgi":
            for pid in os.listdir(configuration.paths.WSGI_PIDFILE_DIR):
                try: os.kill(int(pid), signal.SIGINT)
                except: pass
            return OperationResult()
        else:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.connect(configuration.services.SERVICEMANAGER["address"])
            connection.send(textutils.json_encode({ "command": "restart", "service": service_name }))
            connection.shutdown(socket.SHUT_WR)

            data = ""
            while True:
                received = connection.recv(4096)
                if not received: break
                data += received

            result = textutils.json_decode(data)

            if result["status"] == "ok": return OperationResult()
            else: raise OperationError, result["error"]

class GetServiceLog(Operation):
    def __init__(self):
        Operation.__init__(self, { "service_name": str, "lines": Optional(int) })

    def process(self, db, user, service_name, lines=40):
        logfile_paths = { "manager": configuration.services.SERVICEMANAGER["logfile_path"] }

        for service in configuration.services.SERVICEMANAGER["services"]:
            logfile_paths[service["name"]] = service["logfile_path"]

        logfile_path = logfile_paths.get(service_name)

        if not logfile_path:
            raise OperationError, "unknown service: %s" % service_name

        try: logfile = open(logfile_path)
        except OSError, error:
            raise OperationError, "failed to open logfile: %s" % error.message

        return OperationResult(lines=logfile.read().splitlines()[-lines:])
