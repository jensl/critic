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

import os
import time
import re
import signal

import configuration
import dbutils

from htmlutils import jsify
from request import decodeURIComponent

from extensions.execute import executeProcess, ProcessTimeout, ProcessError
from extensions.manifest import Manifest, PageRole
from extensions.utils import renderTutorial

def execute(db, req, user):
    cursor = db.cursor()

    cursor.execute("""SELECT extensions.id, extensions.author, extensions.name, extensionversions.sha1, roles.path, roles.script, roles.function
                        FROM extensions
                        JOIN extensionversions ON (extensionversions.extension=extensions.id)
                        JOIN extensionroles_page AS roles ON (roles.version=extensionversions.id)
                       WHERE uid=%s""", (user.id,))

    for extension_id, author_id, extension_name, sha1, regexp, script, function in cursor:
        if re.match(regexp, req.path):
            def param(raw):
                parts = raw.split("=", 1)
                if len(parts) == 1: return "%s: null" % jsify(decodeURIComponent(raw))
                else: return "%s: %s" % (jsify(decodeURIComponent(parts[0])), jsify(decodeURIComponent(parts[1])))

            if req.query:
                query = "Object.freeze({ raw: %s, params: Object.freeze({ %s }) })" % (jsify(req.query), ", ".join(map(param, req.query.split("&"))))
            else:
                query = "null"

            headers = "Object.create(null, { %s })" % ", ".join(["%s: { value: %s, enumerable: true }" % (jsify(name), jsify(value)) for name, value in req.getRequestHeaders().items()])

            author = dbutils.User.fromId(db, author_id)

            if sha1 is None: extension_path = os.path.join(configuration.extensions.SEARCH_ROOT, author.name, "CriticExtensions", extension_name)
            else: extension_path = os.path.join(configuration.extensions.INSTALL_DIR, sha1)

            manifest = Manifest.load(extension_path)

            for role in manifest.roles:
                if isinstance(role, PageRole) and role.regexp == regexp and role.script == script and role.function == function:
                    break
            else:
                continue

            argv = ("[%(method)s, %(path)s, %(query)s, %(headers)s]"
                    % { 'method': jsify(req.method),
                        'path': jsify(req.path),
                        'query': query,
                        'headers': headers })

            if req.method == "POST":
                stdin_data = req.read()
            else:
                stdin_data = None

            before = time.time()

            try:
                stdout_data = executeProcess(manifest, role, extension_id, user.id, argv, configuration.extensions.LONG_TIMEOUT,
                                             stdin=stdin_data, rlimit_cpu=60)
            except ProcessTimeout:
                req.setStatus(418, "I'm a teapot")
                return "Extension timed out!"
            except ProcessError, error:
                req.setStatus(418, "I'm a teapot")
                if error.returncode < 0:
                    if -error.returncode == signal.SIGXCPU:
                        return "Extension error: time limit (5 CPU seconds) exceeded\n"
                    else:
                        return "Extension error: terminated by signal %d\n" % -error.returncode
                else:
                    return "Extension error: returned %d\n%s" % (error.returncode, error.stderr)

            after = time.time()

            status = None
            headers = {}

            if not stdout_data:
                return False

            while True:
                try: line, stdout_data = stdout_data.split("\n", 1)
                except:
                    req.setStatus(418, "I'm a teapot")
                    return "Extension error: output format error.\n%r\n" % stdout_data

                if status is None:
                    try: status = int(line.strip())
                    except:
                        req.setStatus(418, "I'm a teapot")
                        return "Extension error: first line should contain only a numeric HTTP status code.\n%r\n" % line
                elif not line:
                    break
                else:
                    try: name, value = line.split(":", 1)
                    except:
                        req.setStatus(418, "I'm a teapot")
                        return "Extension error: header line should be on 'name: value' format.\n%r\n" % line
                    headers[name.strip()] = value.strip()

            if status is None:
                req.setStatus(418, "I'm a teapot")
                return "Extension error: first line should contain only a numeric HTTP status code.\n"

            content_type = "text/plain"

            for name, value in headers.items():
                if name.lower() == "content-type":
                    content_type = value
                    del headers[name]
                else:
                    headers[name] = value

            req.setStatus(status)
            req.setContentType(content_type)

            for name, value in headers.items():
                req.addResponseHeader(name, value)

            if content_type == "text/tutorial":
                req.setContentType("text/html")
                return renderTutorial(db, user, stdout_data)

            if content_type.startswith("text/html"):
                stdout_data += "\n\n<!-- extension execution time: %.2f seconds -->\n" % (after - before)

            return stdout_data

    return False
