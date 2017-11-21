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

import socket
import errno

import base
import configuration
from textutils import json_encode, json_decode, indent

class ChangesetBackgroundServiceError(base.ImplementationError):
    def __init__(self, message):
        super(ChangesetBackgroundServiceError, self).__init__(
            "Changeset background service failed: %s" % message)

def requestChangesets(requests, async=False):
    def uninterruptable(fn):
        while True:
            try:
                return fn()
            except socket.error as error:
                if error[0] == errno.EINTR:
                    continue
                raise

    address = configuration.services.CHANGESET["address"]

    try:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        uninterruptable(lambda: connection.connect(address))
        uninterruptable(lambda: connection.sendall(json_encode({
            "requests": requests,
            "async": async
        })))
        uninterruptable(lambda: connection.shutdown(socket.SHUT_WR))

        data = ""

        while True:
            received = uninterruptable(lambda: connection.recv(4096))
            if not received:
                break
            data += received

        uninterruptable(lambda: connection.close())
    except EnvironmentError as error:
        raise ChangesetBackgroundServiceError(str(error))

    if async:
        return

    if not data:
        raise ChangesetBackgroundServiceError(
            "returned an invalid response: no response")

    try:
        results = json_decode(data)
    except ValueError:
        raise ChangesetBackgroundServiceError(
            "returned an invalid response: %r" % data)

    if not isinstance(results, list):
        # If not a list, the result is probably an error message.
        raise ChangesetBackgroundServiceError(str(results))

    if len(results) != len(requests):
        raise ChangesetBackgroundServiceError("didn't process all requests")

    errors = []

    for result in results:
        if "error" in result:
            errors.append(result["error"])

    if errors:
        raise ChangesetBackgroundServiceError(
            "one or more requests failed:\n%s" % "\n".join(map(indent, errors)))
