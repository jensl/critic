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

import re
import urlparse

import configuration

from auth import AccessDenied
from htmlutils import jsify
from request import decodeURIComponent
from textutils import json_decode, json_encode

from extensions import getExtensionInstallPath
from extensions.extension import Extension, ExtensionError
from extensions.execute import ProcessTimeout, ProcessFailure, executeProcess
from extensions.manifest import Manifest, ManifestError, InjectRole

class InjectError(Exception):
    pass
class InjectIgnored(Exception):
    pass

def processLine(paths, line):
    try:
        command, value = line.split(" ", 1)
    except ValueError:
        raise InjectError("Invalid line in output: %r" % line)

    if command not in ("link", "script", "stylesheet", "preference"):
        raise InjectError("Invalid command: %r" % command)

    value = value.strip()

    try:
        value = json_decode(value)
    except ValueError:
        raise InjectError("Invalid JSON: %r" % value)

    def is_string(value):
        return isinstance(value, basestring)

    if command in ("script", "stylesheet") and not is_string(value):
        raise InjectError("Invalid value for %r: %r (expected string)"
                          % (command, value))
    elif command == "link":
        if isinstance(value, dict):
            if "label" not in value or not is_string(value["label"]):
                raise InjectError("Invalid value for %r: %r (expected attribute 'label' of type string)"
                                  % (command, value))
            elif "url" not in value or not is_string(value["url"]) or value["url"] is None:
                raise InjectError("Invalid value for %r: %r (expected attribute 'url' of type string or null)"
                                  % (command, value))
        # Alternatively support [label, url] (backwards compatibility).
        elif not isinstance(value, list) or len(value) != 2:
            raise InjectError("Invalid value for %r: %r (expected object { \"label\": LABEL, \"url\": URL })"
                              % (command, value))
        elif not is_string(value[0]):
            raise InjectError("Invalid value for %r: %r (expected string at array[0])"
                              % (command, value))
        elif not (is_string(value[1]) or value[1] is None):
            raise InjectError("Invalid value for %r: %r (expected string or null at array[1])"
                              % (command, value))
        else:
            value = { "label": value[0], "url": value[1] }
    elif command == "preference":
        if "config" not in paths:
            raise InjectError("Invalid command: %r only valid on /config page"
                              % command)
        elif not isinstance(value, dict):
            raise InjectError("Invalid value for %r: %r (expected object)"
                              % (command, value))

        for name in ("url", "name", "type", "value", "default", "description"):
            if name not in value:
                raise InjectError("Invalid value for %r: %r (missing attribute %r)"
                                  % (command, value, name))

        preference_url = value["url"]
        preference_name = value["name"]
        preference_type = value["type"]
        preference_value = value["value"]
        preference_default = value["default"]
        preference_description = value["description"]

        if not is_string(preference_url):
            raise InjectError("Invalid value for %r: %r (expected attribute 'url' of type string)"
                              % (command, value))
        elif not is_string(preference_name):
            raise InjectError("Invalid value for %r: %r (expected attribute 'name' of type string)"
                              % (command, value))
        elif not is_string(preference_description):
            raise InjectError("Invalid value for %r: %r (expected attribute 'description' of type string)"
                              % (command, value))

        if is_string(preference_type):
            if preference_type not in ("boolean", "integer", "string"):
                raise InjectError("Invalid value for %r: %r (unsupported preference type)"
                                  % (command, value))

            if preference_type == "boolean":
                type_check = lambda value: isinstance(value, bool)
            elif preference_type == "integer":
                type_check = lambda value: isinstance(value, int)
            else:
                type_check = is_string

            if not type_check(preference_value):
                raise InjectError("Invalid value for %r: %r (type mismatch between 'value' and 'type')"
                                  % (command, value))

            if not type_check(preference_default):
                raise InjectError("Invalid value for %r: %r (type mismatch between 'default' and 'type')"
                                  % (command, value))
        else:
            if not isinstance(preference_type, list):
                raise InjectError("Invalid value for %r: %r (invalid 'type', expected string or array)"
                                  % (command, value))

            for index, choice in enumerate(preference_type):
                if not isinstance(choice, dict) \
                        or not isinstance(choice.get("value"), basestring) \
                        or not isinstance(choice.get("title"), basestring):
                    raise InjectError("Invalid value for %r: %r (invalid preference choice: %r)"
                                      % (command, value, choice))

            choices = set([choice["value"] for choice in preference_type])

            if not is_string(preference_value) or preference_value not in choices:
                raise InjectError("Invalid value for %r: %r ('value' not among valid choices)"
                                  % (command, value))

            if not is_string(preference_default) or preference_default not in choices:
                raise InjectError("Invalid value for %r: %r ('default' not among valid choices)"
                                  % (command, value))

    return (command, value)

def execute(db, req, user, document, links, injected, profiler=None):
    cursor = db.cursor()

    installs = Extension.getInstalls(db, user)

    def get_matching_path(path_regexp):
        if re.match(path_regexp, req.path):
            return (req.path, req.query)
        elif re.match(path_regexp, req.original_path):
            return (req.original_path, req.original_query)
        else:
            return None, None

    query = None

    for extension_id, version_id, version_sha1, is_universal in installs:
        handlers = []

        try:
            if version_id is not None:
                cursor.execute("""SELECT script, function, path
                                    FROM extensionroles
                                    JOIN extensioninjectroles ON (role=id)
                                   WHERE version=%s
                                ORDER BY id ASC""",
                               (version_id,))

                for script, function, path_regexp in cursor:
                    path, query = get_matching_path(path_regexp)
                    if path is not None:
                        handlers.append((path, query, script, function))

                if not handlers:
                    continue

                extension = Extension.fromId(db, extension_id)
                manifest = Manifest.load(getExtensionInstallPath(version_sha1))
            else:
                extension = Extension.fromId(db, extension_id)
                manifest = Manifest.load(extension.getPath())

                for role in manifest.roles:
                    if isinstance(role, InjectRole):
                        path, query = get_matching_path(role.regexp)
                        if path is not None:
                            handlers.append((path, query, role.script, role.function))

                if not handlers:
                    continue

            def construct_query(query):
                if not query:
                    return "null"

                params = urlparse.parse_qs(query, keep_blank_values=True)

                for key in params:
                    values = params[key]
                    if len(values) == 1:
                        if not values[0]:
                            params[key] = None
                        else:
                            params[key] = values[0]

                return ("Object.freeze({ raw: %s, params: Object.freeze(%s) })"
                        % (json_encode(query), json_encode(params)))

            preferences = None
            commands = []

            for path, query, script, function in handlers:
                argv = "[%s, %s]" % (jsify(path), construct_query(query))

                try:
                    stdout_data = executeProcess(
                        db, manifest, "inject", script, function, extension_id, user.id, argv,
                        configuration.extensions.SHORT_TIMEOUT)
                except ProcessTimeout as error:
                    raise InjectError(error.message)
                except ProcessFailure as error:
                    if error.returncode < 0:
                        raise InjectError("Process terminated by signal %d." % -error.returncode)
                    else:
                        raise InjectError("Process returned %d.\n%s" % (error.returncode, error.stderr))
                except AccessDenied:
                    raise InjectIgnored()

                for line in stdout_data.splitlines():
                    if line.strip():
                        commands.append(processLine(path, line.strip()))

            for command, value in commands:
                if command == "script":
                    document.addExternalScript(value, use_static=False, order=1)
                elif command == "stylesheet":
                    document.addExternalStylesheet(value, use_static=False, order=1)
                elif command == "link":
                    for index, (_, label, _, _) in enumerate(links):
                        if label == value["label"]:
                            if value["url"] is None:
                                del links[index]
                            else:
                                links[index][0] = value["url"]
                            break
                    else:
                        if value["url"] is not None:
                            links.append([value["url"], value["label"], None, None])
                elif command == "preference":
                    if not preferences:
                        preferences = []
                        injected.setdefault("preferences", []).append(
                            (extension.getName(), extension.getAuthor(db), preferences))
                    preferences.append(value)

            if profiler:
                profiler.check("inject: %s" % extension.getKey())
        except ExtensionError as error:
            document.comment("\n\n[%s] Extension error:\nInvalid extension:\n%s\n\n"
                             % (error.extension.getKey(), error.message))
        except ManifestError as error:
            document.comment("\n\n[%s] Extension error:\nInvalid MANIFEST:\n%s\n\n"
                             % (extension.getKey(), error.message))
        except InjectError as error:
            document.comment("\n\n[%s] Extension error:\n%s\n\n"
                             % (extension.getKey(), error.message))
        except InjectIgnored:
            pass
