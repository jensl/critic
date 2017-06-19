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

import time
import re

import configuration

from htmlutils import jsify
from request import decodeURIComponent

from extensions import getExtensionInstallPath
from extensions.extension import Extension, ExtensionError
from extensions.execute import ProcessTimeout, ProcessFailure, executeProcess
from extensions.manifest import Manifest, ManifestError, PageRole
from extensions.utils import renderTutorial

def execute(db, req, user):
    cursor = db.cursor()

    installs = Extension.getInstalls(db, user)

    argv = None
    stdin_data = None

    for extension_id, version_id, version_sha1, is_universal in installs:
        handlers = []

        if version_id is not None:
            cursor.execute("""SELECT script, function, path
                                FROM extensionroles
                                JOIN extensionpageroles ON (role=id)
                               WHERE version=%s
                            ORDER BY id ASC""",
                           (version_id,))

            for script, function, path_regexp in cursor:
                if re.match(path_regexp, req.path):
                    handlers.append((script, function))

            if not handlers:
                continue

            extension_path = getExtensionInstallPath(version_sha1)
            manifest = Manifest.load(extension_path)
        else:
            try:
                extension = Extension.fromId(db, extension_id)
            except ExtensionError:
                # If the author/hosting user no longer exists, or the extension
                # directory no longer exists or is inaccessible, ignore the
                # extension.
                continue

            try:
                manifest = Manifest.load(extension.getPath())
            except ManifestError:
                # If the MANIFEST is missing or invalid, we can't know whether
                # the extension has a page role handling the path, so assume it
                # doesn't and ignore it.
                continue

            for role in manifest.roles:
                if isinstance(role, PageRole) and re.match(role.regexp, req.path):
                    handlers.append((role.script, role.function))

            if not handlers:
                continue

        if argv is None:
            def param(raw):
                parts = raw.split("=", 1)
                if len(parts) == 1:
                    return "%s: null" % jsify(decodeURIComponent(raw))
                else:
                    return "%s: %s" % (jsify(decodeURIComponent(parts[0])),
                                       jsify(decodeURIComponent(parts[1])))

            if req.query:
                query = ("Object.freeze({ raw: %s, params: Object.freeze({ %s }) })"
                         % (jsify(req.query),
                            ", ".join(map(param, req.query.split("&")))))
            else:
                query = "null"

            headers = ("Object.freeze({ %s })"
                       % ", ".join(("%s: %s" % (jsify(name), jsify(value)))
                                   for name, value in req.getRequestHeaders().items()))

            argv = ("[%(method)s, %(path)s, %(query)s, %(headers)s]"
                    % { 'method': jsify(req.method),
                        'path': jsify(req.path),
                        'query': query,
                        'headers': headers })

        if req.method == "POST":
            if stdin_data is None:
                stdin_data = req.read()

        for script, function in handlers:
            before = time.time()

            try:
                stdout_data = executeProcess(
                    db, manifest, "page", script, function, extension_id, user.id,
                    argv, configuration.extensions.LONG_TIMEOUT, stdin=stdin_data)
            except ProcessTimeout as error:
                req.setStatus(500, "Extension Timeout")
                return error.message
            except ProcessFailure as error:
                req.setStatus(500, "Extension Failure")
                if error.returncode < 0:
                    return ("Extension failure: terminated by signal %d\n"
                            % -error.returncode)
                else:
                    return ("Extension failure: returned %d\n%s"
                            % (error.returncode, error.stderr))

            after = time.time()

            status = None
            headers = {}

            if not stdout_data:
                return False

            while True:
                try: line, stdout_data = stdout_data.split("\n", 1)
                except:
                    req.setStatus(500, "Extension Error")
                    return "Extension error: output format error.\n%r\n" % stdout_data

                if status is None:
                    try: status = int(line.strip())
                    except:
                        req.setStatus(500, "Extension Error")
                        return "Extension error: first line should contain only a numeric HTTP status code.\n%r\n" % line
                elif not line:
                    break
                else:
                    try: name, value = line.split(":", 1)
                    except:
                        req.setStatus(500, "Extension Error")
                        return "Extension error: header line should be on 'name: value' format.\n%r\n" % line
                    headers[name.strip()] = value.strip()

            if status is None:
                req.setStatus(500, "Extension Error")
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
