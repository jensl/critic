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

import base
import configuration
import syntaxhighlight

from textutils import json_encode, json_decode

class HighlightBackgroundServiceError(base.ImplementationError):
    def __init__(self, message):
        super(HighlightBackgroundServiceError, self).__init__(
            "Highlight background service failed: %s" % message)

def requestHighlights(repository, sha1s):
    requests = [{ "repository_path": repository.path, "sha1": sha1, "path": path, "language": language }
                for sha1, (path, language) in sha1s.items()
                if not syntaxhighlight.isHighlighted(sha1, language)]

    if not requests: return

    try:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.connect(configuration.services.HIGHLIGHT["address"])
        connection.send(json_encode(requests))
        connection.shutdown(socket.SHUT_WR)

        data = ""

        while True:
            received = connection.recv(4096)
            if not received: break
            data += received

        connection.close()
    except socket.error as error:
        raise HighlightBackgroundServiceError(error[1])

    try:
        results = json_decode(data)
    except ValueError:
        raise HighlightBackgroundServiceError(
            "returned an invalid response (%r)" % data)

    if type(results) != list:
        # If not a list, the result is probably an error message.
        raise HighlightBackgroundServiceError(str(results))

    if len(results) != len(requests):
        raise HighlightBackgroundServiceError("didn't process all requests")
