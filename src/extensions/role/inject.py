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
import re
import signal

import configuration
import dbutils

from communicate import ProcessTimeout, ProcessError
from htmlutils import jsify
from request import decodeURIComponent
from textutils import json_decode

from extensions import getExtensionInstallPath
from extensions.extension import Extension
from extensions.execute import executeProcess
from extensions.manifest import Manifest, ManifestError, InjectRole

def execute(db, paths, args, user, document, links, injected, profiler=None):
    cursor = db.cursor()

    cursor.execute("""SELECT extensions.id, extensions.author, extensions.name, extensionversions.sha1, roles.path, roles.script, roles.function
                        FROM extensions
                        JOIN extensionversions ON (extensionversions.extension=extensions.id)
                        JOIN extensionroles_inject AS roles ON (roles.version=extensionversions.id)
                       WHERE uid=%s""", (user.id,))

    for extension_id, author_id, extension_name, sha1, regexp, script, function in cursor:
        for path in paths:
            match = re.match(regexp, path)
            if match: break

        if match:
            def param(raw):
                parts = raw.split("=", 1)
                if len(parts) == 1: return "%s: null" % jsify(decodeURIComponent(raw))
                else: return "%s: %s" % (jsify(decodeURIComponent(parts[0])), jsify(decodeURIComponent(parts[1])))

            if args:
                query = "Object.freeze({ raw: %s, params: Object.freeze({ %s }) })" % (jsify(args), ", ".join(map(param, args.split("&"))))
            else:
                query = "null"

            author = dbutils.User.fromId(db, author_id)

            if sha1 is None:
                extension_path = os.path.join(configuration.extensions.SEARCH_ROOT, author.name, "CriticExtensions", extension_name)
            else:
                extension_path = os.path.join(configuration.extensions.INSTALL_DIR, sha1)

            class Error(Exception):
                pass

            try:
                try:
                    manifest = Manifest.load(extension_path)
                except ManifestError, error:
                    raise Error("Invalid MANIFEST:\n%s" % error.message)

                for role in manifest.roles:
                    if isinstance(role, InjectRole) and role.regexp == regexp and role.script == script and role.function == function:
                        break
                else:
                    continue

                argv = "[%(path)s, %(query)s]" % { 'path': jsify(path), 'query': query }

                try:
                    stdout_data = executeProcess(manifest, role, extension_id, user.id, argv, configuration.extensions.SHORT_TIMEOUT)
                except ProcessTimeout:
                    raise Error("Timeout after %d seconds." % configuration.extensions.SHORT_TIMEOUT)
                except ProcessError, error:
                    if error.returncode < 0:
                        if -error.returncode == signal.SIGXCPU:
                            raise Error("CPU time limit (5 seconds) exceeded.")
                        else:
                            raise Error("Process terminated by signal %d." % -error.returncode)
                    else:
                        raise Error("Process returned %d.\n%s" % (error.returncode, error.stderr))

                commands = []

                def processLine(line):
                    try:
                        command, value = line.split(" ", 1)
                    except ValueError:
                        raise Error("Invalid line in output: %r" % line)

                    if command not in ("link", "script", "stylesheet", "preference"):
                        raise Error("Invalid command: %r" % command)

                    try:
                        value = json_decode(value.strip())
                    except ValueError:
                        raise Error("Invalid JSON: %r" % value.strip())

                    def is_string(value):
                        return isinstance(value, basestring)

                    if command in ("script", "stylesheet") and not is_string(value):
                        raise Error("Invalid value for %r: %r (expected string)" % (command, value))
                    elif command == "link":
                        if not isinstance(value, list) or len(value) != 2:
                            raise Error("Invalid value for %r: %r (expected array of length two)" % (command, value))
                        elif not is_string(value[0]):
                            raise Error("Invalid value for %r: %r (expected string at array[0])" % (command, value))
                        elif not (is_string(value[1]) or value[1] is None):
                            raise Error("Invalid value for %r: %r (expected string or null at array[1])" % (command, value))
                    elif command == "preference":
                        if path != "config":
                            raise Error("Invalid command: %r only valid on /config page" % command)
                        elif not isinstance(value, dict):
                            raise Error("Invalid value for %r: %r (expected object)" % (command, value))

                        for name in ("url", "name", "type", "value", "default", "description"):
                            if name not in value:
                                raise Error("Invalid value for %r: %r (missing property: %r)" % (command, value, name))

                        preference_url = value["url"]
                        preference_name = value["name"]
                        preference_type = value["type"]
                        preference_value = value["value"]
                        preference_default = value["default"]
                        preference_description = value["description"]

                        if not is_string(preference_url):
                            raise Error("Invalid value for %r: %r (expected string as %r)" % (command, value, "url"))
                        elif not is_string(preference_name):
                            raise Error("Invalid value for %r: %r (expected string as %r)" % (command, value, "name"))
                        elif not is_string(preference_description):
                            raise Error("Invalid value for %r: %r (expected string as %r)" % (command, value, "description"))

                        if is_string(preference_type):
                            if preference_type not in ("boolean", "integer", "string"):
                                raise Error("Invalid value for %r: %r (unsupported preference type)" % (command, value))

                            if preference_type == "boolean": type_check = lambda value: isinstance(value, bool)
                            elif preference_type == "integer": type_check = lambda value: isinstance(value, int)
                            else: type_check = is_string

                            if not type_check(preference_value):
                                raise Error("Invalid value for %r: %r (type mismatch between %r and %r)" % (command, value, "value", "type"))

                            if not type_check(preference_default):
                                raise Error("Invalid value for %r: %r (type mismatch between %r and %r)" % (command, value, "default", "type"))
                        else:
                            if not isinstance(preference_type, list):
                                raise Error("Invalid value for %r: %r (invalid %r, expected string or array)" % (command, value, "type"))

                            for index, choice in enumerate(preference_type):
                                if not isinstance(choice, dict) \
                                        or not isinstance(choice.get("value"), basestring) \
                                        or not isinstance(choice.get("title"), basestring):
                                    raise Error("Invalid value for %r: %r (invalid preference choice: %r)" % (command, value, choice))

                            choices = set([choice["value"] for choice in preference_type])

                            if not is_string(preference_value) or preference_value not in choices:
                                raise Error("Invalid value for %r: %r (%r not among valid choices)" % (command, value, "value"))

                            if not is_string(preference_default) or preference_default not in choices:
                                raise Error("Invalid value for %r: %r (%r not among valid choices)" % (command, value, "default"))

                    commands.append((command, value))
                    return True

                failed = False

                for line in stdout_data.splitlines():
                    if line.strip():
                        if not processLine(line.strip()):
                            failed = True
                            break

                if not failed:
                    preferences = None

                    for command, value in commands:
                        if command == "script":
                            document.addExternalScript(value, use_static=False, order=1)
                        elif command == "stylesheet":
                            document.addExternalStylesheet(value, use_static=False, order=1)
                        elif command == "link":
                            for index, (url, label, not_current, style, title) in enumerate(links):
                                if label == value[0]:
                                    if value[1] is None: del links[index]
                                    else: links[index][0] = value[0]
                                    break
                            else:
                                if value[1] is not None:
                                    links.append([value[1], value[0], True, None, None])
                        elif command == "preference":
                            if not preferences:
                                preferences = []
                                injected.setdefault("preferences", []).append((extension_name, author, preferences))
                            preferences.append(value)
            except Error, error:
                document.comment("\n\n[%s/%s] Extension error:\n%s\n\n" % (author.name, extension_name, error.message))

            if profiler:
                profiler.check("inject: %s/%s" % (author.name, extension_name))
