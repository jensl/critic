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

import configuration
import syntaxhighlight
import socket

try: from json import dumps as json_encode, loads as json_decode
except: from cjson import encode as json_encode, decode as json_decode

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
    except socket.error, error:
        raise Exception, "Syntax highlighting background service failed: %s" % error[1]

    try:
        results = json_decode(data)
    except:
        raise Exception, "Syntax highlighting background service failed: returned an invalid response (%r)" % data

    if type(results) != list:
        raise Exception, "Syntax highlighting background service failed: %s" % str(results)

    assert len(results) == len(requests)
