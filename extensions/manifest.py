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

import configuration
from textutils import json_decode

RE_ROLE_Page = re.compile(r"^\[Page (.*)\]$", re.IGNORECASE)
RE_ROLE_Inject = re.compile(r"^\[Inject (.*)\]$", re.IGNORECASE)
RE_ROLE_ProcessCommits = re.compile(r"^\[ProcessCommits\]$", re.IGNORECASE)
RE_ROLE_ProcessChanges = re.compile(r"^\[ProcessChanges\]$", re.IGNORECASE)
RE_ROLE_Scheduled = re.compile(r"^\[Scheduled\]$", re.IGNORECASE)

class ManifestError(Exception):
    pass

class Role:
    def __init__(self):
        self.script = None
        self.function = None
        self.description = None
        self.installed = None

    def install(self, cursor, version_id, user):
        cursor.execute("INSERT INTO extensionroles (uid, version, script, function) VALUES (%s, %s, %s, %s) RETURNING id",
                       (user.id, version_id, self.script, self.function))
        return cursor.fetchone()[0]

    def process(self, name, value, location):
        if name == "description":
            self.description = value
            return True
        elif name == "script":
            self.script = value
            return True
        elif name == "function":
            self.function = value
            return True
        else:
            return False

    def check(self, location):
        if not self.description:
            raise ManifestError("%s:%d: manifest error: expected role description" % location)
        elif not self.script:
            raise ManifestError("%s:%d: manifest error: expected role script" % location)
        elif not self.function:
            raise ManifestError("%s:%d: manifest error: expected role function" % location)

class URLRole(Role):
    def __init__(self, pattern):
        Role.__init__(self)
        self.pattern = pattern
        self.regexp = "^" + re.sub(r"[\|\[\](){}^$+]",
                                   lambda match: '\\' + match.group(0),
                                   pattern.replace('.', '\\.').replace('?', '.').replace('*', '.*')) + "$"

class PageRole(URLRole):
    def __init__(self, pattern):
        URLRole.__init__(self, pattern)

    def name(self):
        return "Page"

    def install(self, cursor, version_id, user):
        role_id = Role.install(self, cursor, version_id, user)
        cursor.execute("INSERT INTO extensionpageroles (role, path) VALUES (%s, %s)",
                       (role_id, self.regexp))
        return role_id

class InjectRole(URLRole):
    def __init__(self, pattern):
        URLRole.__init__(self, pattern)

    def name(self):
        return "Inject"

    def install(self, cursor, version_id, user):
        role_id = Role.install(self, cursor, version_id, user)
        cursor.execute("INSERT INTO extensioninjectroles (role, path) VALUES (%s, %s)",
                       (role_id, self.regexp))
        return role_id

class ProcessCommitsRole(Role):
    def __init__(self):
        Role.__init__(self)

    def name(self):
        return "ProcessCommits"

    def install(self, cursor, version_id, user):
        role_id = Role.install(self, cursor, version_id, user)
        cursor.execute("INSERT INTO extensionprocesscommitsroles (role) VALUES (%s)",
                       (role_id,))
        return role_id

class ProcessChangesRole(Role):
    def __init__(self):
        Role.__init__(self)

    def name(self):
        return "ProcessChanges"

    def install(self, cursor, version_id, user):
        role_id = Role.install(self, cursor, version_id, user)
        cursor.execute("INSERT INTO extensionprocesschangesroles (role, skip) SELECT %s, MAX(id) FROM batches",
                       (role_id,))
        return role_id

class ScheduledRole(Role):
    def __init__(self):
        Role.__init__(self)
        self.frequency = None
        self.at = None

    def name(self):
        return "Scheduled"

    def install(self, cursor, version_id, user):
        role_id = Role.install(self, cursor, version_id, user)
        cursor.execute("INSERT INTO extensionscheduledroles (role, frequency, at) VALUES (%s, %s, %s)",
                       (role_id, self.frequency, self.at))
        return role_id

    def process(self, name, value, location):
        if Role.process(self, name, value, location):
            return True
        elif name == "frequency":
            if value in ("monthly", "weekly", "daily", "hourly"):
                self.frequency = value.lower()
            else:
                raise ManifestError("%s:%d: invalid frequency: must be one of 'monthly', 'weekly', 'daily' and 'hourly'" % location)
        elif name == "at":
            self.at = value.lower()
        else:
            return False
        return True

    def check(self, location):
        Role.check(self, location)

        if not self.frequency:
            raise ManifestError("%s:%d: manifest error: expected role parameter 'frequency'" % location)
        if not self.at:
            raise ManifestError("%s:%d: manifest error: expected role parameter 'at'" % location)

        if self.frequency == "monthly":
            match = re.match("(\d+) (\d{2}):(\d{2})$", self.at)
            if match:
                date = int(match.group(1).lstrip("0"))
                hour = int(match.group(2).lstrip("0"))
                minute = int(match.group(3).lstrip("0"))
                if (1 <= date <= 31) and (0 <= hour <= 23) and (0 <= minute <= 59):
                    return
            raise ManifestError("invalid at specification for monthly trigger, must be 'D HH:MM' (D = day in month; 1-31), is '%s'" % self.at)
        elif self.frequency == "weekly":
            match = re.match("(?:mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?) (\d{2}):(\d{2})$", self.at)
            if match:
                hour = int(match.group(1).lstrip("0"))
                minute = int(match.group(2).lstrip("0"))
                if (0 <= hour <= 23) and (0 <= minute <= 59):
                    return
            raise ManifestError("invalid at specification for weekly trigger, must be 'WEEKDAY HH:MM' (WEEKDAY = mon|tue|wed|thu|fri|sat|sun), is '%s'" % self.at)
        elif self.frequency == "daily":
            match = re.match("(\d{2}):(\d{2})$", self.at)
            if match:
                hour = int(match.group(1).lstrip("0"))
                minute = int(match.group(2).lstrip("0"))
                if (0 <= hour <= 23) and (0 <= minute <= 59):
                    return
            raise ManifestError("invalid at specification for daily trigger, must be 'HH:MM'")
        elif self.frequency == "hourly":
            match = re.match("(\d{2})$", self.at)
            if match:
                minute = int(match.group(1).lstrip("0"))
                if (0 <= minute <= 59):
                    return
            raise ManifestError("invalid at specification for hourly trigger, must be 'MM'")

class Manifest:
    def __init__(self, path, source=None):
        self.path = path
        self.source = source
        self.author = []
        self.description = None
        self.flavor = configuration.extensions.DEFAULT_FLAVOR
        self.roles = []
        self.status = None
        self.hidden = False

    def read(self):
        path = os.path.join(self.path, "MANIFEST")

        if self.source: lines = self.source.splitlines()
        else: lines = open(path).readlines()

        lines = map(str.strip, lines)

        def process(value):
            value = value.strip()
            if value[0] == '"' == value[-1]:
                return json_decode(value)
            else:
                return value

        role = None

        for index, line in enumerate(lines):
            if not line or line.lstrip().startswith("#"): continue

            location = "%s:%d" % (path, index + 1)

            if not role:
                try:
                    name, value = line.split("=", 1)
                    if name.strip().lower() == "author":
                        self.author.append(process(value))
                        continue
                    elif name.strip().lower() == "description":
                        self.description = process(value)
                        continue
                    elif name.strip().lower() == "flavor":
                        self.flavor = process(value)
                        if self.flavor not in configuration.extensions.FLAVORS:
                            raise ManifestError("%s: manifest error: unsupported 'flavor', supported values are: %s"
                                                % (location, ", ".join(map(repr, configuration.extensions.FLAVORS.keys()))))
                        continue
                    elif name.strip().lower() == "hidden":
                        value = process(value).lower()
                        if value in ("true", "yes"):
                            self.hidden = True
                        elif value not in ("false", "no"):
                            raise ManifestError("%s: manifest error: valid values for 'hidden' are 'true'/'yes' and 'false'/'no'" % location)
                        continue
                except:
                    pass

                if not self.author:
                    raise ManifestError("%s: manifest error: expected extension author" % location)
                elif not self.description:
                    raise ManifestError("%s: manifest error: expected extension description" % location)

            if role:
                if "=" in line:
                    name, value = line.split("=", 1)
                    if role.process(name.strip().lower(), process(value), location):
                        continue

                role.check(location)

                self.roles.append(role)

            match = RE_ROLE_Page.match(line)
            if match:
                role = PageRole(match.group(1))
                continue

            match = RE_ROLE_Inject.match(line)
            if match:
                role = InjectRole(match.group(1))
                continue

            match = RE_ROLE_ProcessCommits.match(line)
            if match:
                role = ProcessCommitsRole()
                continue

            match = RE_ROLE_ProcessChanges.match(line)
            if match:
                role = ProcessChangesRole()
                continue

            match = RE_ROLE_Scheduled.match(line)
            if match:
                role = ScheduledRole()
                continue

            raise ManifestError("%s: manifest error: unexpected line: %r" % (location, line))

        if not self.author:
            raise ManifestError("%s: manifest error: expected extension author" % path)
        elif not self.description:
            raise ManifestError("%s: manifest error: expected extension description" % path)

        if role:
            if not role.description:
                raise ManifestError("%s: manifest error: expected role description" % path)
            elif not role.script:
                raise ManifestError("%s: manifest error: expected role script" % path)
            elif not role.function:
                raise ManifestError("%s: manifest error: expected role function" % path)
            else:
                self.roles.append(role)

        if not self.roles:
            raise ManifestError("%s: manifest error: no roles defined" % path)

    @staticmethod
    def load(extension_path):
        manifest = Manifest(extension_path)
        manifest.read()
        return manifest
