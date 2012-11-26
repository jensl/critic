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
import os.path
import sys
import re
import time
import signal

from textutils import json_encode, json_decode

import gitutils
from htmlutils import jsify
from request import decodeURIComponent
from log.commitset import CommitSet
from subprocess import Popen as process, PIPE, check_call, check_output, CalledProcessError
import configuration

import dbutils
import changeset.utils

RE_ROLE_Page = re.compile(r"^\[Page (.*)\]$", re.IGNORECASE)
RE_ROLE_Inject = re.compile(r"^\[Inject (.*)\]$", re.IGNORECASE)
RE_ROLE_ProcessCommits = re.compile(r"^\[ProcessCommits\]$", re.IGNORECASE)
RE_ROLE_ProcessChanges = re.compile(r"^\[ProcessChanges\]$", re.IGNORECASE)

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

class URLRole(Role):
    def __init__(self, pattern):
        Role.__init__(self)
        self.pattern = pattern
        self.regexp = "^" + re.sub(r"[\|\[\](){}^$+]", lambda match: '\\' + match.group(0), pattern.replace('.', '\\.').replace('?', '.').replace('*', '.*')) + "$"

class PageRole(URLRole):
    def __init__(self, pattern):
        URLRole.__init__(self, pattern)

    def install(self, cursor, version_id, user):
        role_id = Role.install(self, cursor, version_id, user)
        cursor.execute("INSERT INTO extensionpageroles (role, path) VALUES (%s, %s)",
                       (role_id, self.regexp))
        return role_id

class InjectRole(URLRole):
    def __init__(self, pattern):
        URLRole.__init__(self, pattern)

    def install(self, cursor, version_id, user):
        role_id = Role.install(self, cursor, version_id, user)
        cursor.execute("INSERT INTO extensioninjectroles (role, path) VALUES (%s, %s)",
                       (role_id, self.regexp))
        return role_id

class ProcessCommitsRole(Role):
    def __init__(self):
        Role.__init__(self)

    def install(self, cursor, version_id, user):
        role_id = Role.install(self, cursor, version_id, user)
        cursor.execute("INSERT INTO extensionprocesscommitsroles (role) VALUES (%s)",
                       (role_id,))
        return role_id

class ProcessChangesRole(Role):
    def __init__(self):
        Role.__init__(self)

    def install(self, cursor, version_id, user):
        role_id = Role.install(self, cursor, version_id, user)
        cursor.execute("INSERT INTO extensionprocesschangesroles (role, skip) SELECT %s, MAX(id) FROM batches",
                       (role_id,))
        return role_id

class ManifestError(Exception):
    pass

class Manifest:
    def __init__(self, path, source=None):
        self.path = path
        self.source = source
        self.author = []
        self.description = None
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
            if not line: continue

            if not role:
                try:
                    name, value = line.split("=", 1)
                    if name.strip().lower() == "author":
                        self.author.append(process(value))
                        continue
                    elif name.strip().lower() == "description":
                        self.description = process(value)
                        continue
                    elif name.strip().lower() == "hidden":
                        value = process(value).lower()
                        if value in ("true", "yes"):
                            self.hidden = True
                        elif value not in ("false", "no"):
                            raise ManifestError, "%s:%d: manifest error: valid values for 'hidden' are 'true'/'yes' and 'false'/'no'" % (path, index + 1)
                        continue
                except:
                    pass

                if not self.author:
                    raise ManifestError, "%s:%d: manifest error: expected extension author" % (path, index + 1)
                elif not self.description:
                    raise ManifestError, "%s:%d: manifest error: expected extension description" % (path, index + 1)

            if role:
                try:
                    name, value = line.split("=", 1)
                    if name.strip().lower() == "description":
                        role.description = process(value)
                        continue
                    elif name.strip().lower() == "script":
                        role.script = process(value)
                        continue
                    elif name.strip().lower() == "function":
                        role.function = process(value)
                        continue
                except:
                    pass

                if not role.description:
                    raise ManifestError, "%s:%d: manifest error: expected role description" % (path, index + 1)
                elif not role.script:
                    raise ManifestError, "%s:%d: manifest error: expected role script" % (path, index + 1)
                elif not role.function:
                    raise ManifestError, "%s:%d: manifest error: expected role function" % (path, index + 1)
                else:
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

            raise ManifestError, "%s:%d: manifest error: unexpected line: %r" % (path, index + 1, line)

        if not self.author:
            raise ManifestError, "%s: manifest error: expected extension author" % path
        elif not self.description:
            raise ManifestError, "%s: manifest error: expected extension description" % path

        if role:
            if not role.description:
                raise ManifestError, "%s: manifest error: expected role description" % path
            elif not role.script:
                raise ManifestError, "%s: manifest error: expected role script" % path
            elif not role.function:
                raise ManifestError, "%s: manifest error: expected role function" % path
            else:
                self.roles.append(role)

        if not self.roles:
            raise ManifestError, "%s: manifest error: no roles defined" % path

class Extension:
    def __init__(self, author_name, extension_name):
        self.__author_name = author_name
        self.__extension_name = extension_name
        self.__path = os.path.join(configuration.extensions.SEARCH_ROOT, author_name, "CriticExtensions", extension_name)

    def getAuthorName(self):
        return self.__author_name

    def getName(self):
        return self.__extension_name

    def getKey(self):
        return "%s/%s" % (self.__author_name, self.__extension_name)

    def getPath(self):
        return self.__path

    def getVersions(self):
        try:
            branches = map(str.strip, check_output([configuration.executables.GIT, "branch"], cwd=self.__path).splitlines())
            return [branch[8:] for branch in branches if branch.startswith("version/")]
        except CalledProcessError:
            # Not a git repository => no versions (except "Live").
            return []

    def readManifest(self, version=None):
        if version is None: source = None
        else: source = check_output([configuration.executables.GIT, "cat-file", "blob", "version/%s:MANIFEST" % version], cwd=self.__path)

        manifest = Manifest(self.__path, source)
        manifest.read()
        return manifest

    def getCurrentSHA1(self, version):
        return check_output([configuration.executables.GIT, "rev-parse", "--verify", "version/%s" % version], cwd=self.__path).strip()

    def prepareVersionSnapshot(self, version):
        sha1 = self.getCurrentSHA1(version)

        if not os.path.isdir(os.path.join(configuration.extensions.INSTALL_DIR, sha1)):
            git_archive = process([configuration.executables.GIT, "archive", "--format=tar", "--prefix=%s/" % sha1, sha1], stdout=PIPE, cwd=self.__path)
            check_call([configuration.executables.TAR, "x"], stdin=git_archive.stdout, cwd=configuration.extensions.INSTALL_DIR)

        return sha1

    def getAuthor(self, db):
        return dbutils.User.fromName(db, self.__author_name)

    def getExtensionID(self, db, create=False):
        author_id = self.getAuthor(db).id

        cursor = db.cursor()
        cursor.execute("""SELECT extensions.id
                            FROM extensions
                           WHERE extensions.author=%s
                             AND extensions.name=%s""",
                       (author_id, self.__extension_name))
        row = cursor.fetchone()

        if row: return row[0]
        elif create:
            cursor.execute("""INSERT INTO extensions (author, name)
                              VALUES (%s, %s)
                           RETURNING id""",
                           (author_id, self.__extension_name))
            return cursor.fetchone()[0]
        else: return None

    def getInstalledVersion(self, db, user):
        """Return (sha1, name) of the version currently installed by the user.

        If the user doesn't have the extension installed, return (False, False).
        If the user has the "live" version installed, return (None, None).

        """
        extension_id = self.getExtensionID(db)

        if extension_id is None:
            # An extension is recorded in the database and assigned an ID the
            # first time it's installed.  If it doesn't have an ID, then no user
            # can have any version of it installed.
            return (False, False)

        cursor = db.cursor()
        cursor.execute("""SELECT DISTINCT extensionversions.sha1, extensionversions.name
                            FROM extensionversions
                            JOIN extensionroles ON (extensionroles.version=extensionversions.id)
                           WHERE extensionversions.extension=%s
                             AND extensionroles.uid=%s""",
                       (extension_id, user.id))
        versions = set(cursor)

        if len(versions) > 1:
            raise Exception, "Error, error!  Multple versions installed.  This should not happen."

        if versions: return versions.pop()
        else: return (False, False)

    def getInstallationStatus(self, db, user, version=None):
        author = self.getAuthor(db)
        manifest = self.readManifest(version)

        cursor = db.cursor()
        version_ids = set()
        installed_roles = 0

        for role in manifest.roles:
            if isinstance(role, PageRole):
                cursor.execute("""SELECT extensionversions.id
                                    FROM extensions
                                    JOIN extensionversions ON (extensionversions.extension=extensions.id)
                                    JOIN extensionroles_page ON (extensionroles_page.version=extensionversions.id)
                                   WHERE extensions.author=%s
                                     AND extensions.name=%s
                                     AND extensionroles_page.uid=%s
                                     AND extensionroles_page.path=%s
                                     AND extensionroles_page.script=%s
                                     AND extensionroles_page.function=%s""",
                               (author.id, self.__extension_name, user.id, role.regexp, role.script, role.function))
            elif isinstance(role, InjectRole):
                cursor.execute("""SELECT extensionversions.id
                                    FROM extensions
                                    JOIN extensionversions ON (extensionversions.extension=extensions.id)
                                    JOIN extensionroles_inject ON (extensionroles_inject.version=extensionversions.id)
                                   WHERE extensions.author=%s
                                     AND extensions.name=%s
                                     AND extensionroles_inject.uid=%s
                                     AND extensionroles_inject.path=%s
                                     AND extensionroles_inject.script=%s
                                     AND extensionroles_inject.function=%s""",
                               (author.id, self.__extension_name, user.id, role.regexp, role.script, role.function))
            elif isinstance(role, ProcessCommitsRole):
                cursor.execute("""SELECT extensionversions.id
                                    FROM extensions
                                    JOIN extensionversions ON (extensionversions.extension=extensions.id)
                                    JOIN extensionroles_processcommits ON (extensionroles_processcommits.version=extensionversions.id)
                                   WHERE extensions.author=%s
                                     AND extensions.name=%s
                                     AND extensionroles_processcommits.uid=%s
                                     AND extensionroles_processcommits.script=%s
                                     AND extensionroles_processcommits.function=%s""",
                               (author.id, self.__extension_name, user.id, role.script, role.function))
            elif isinstance(role, ProcessChangesRole):
                cursor.execute("""SELECT extensionversions.id
                                    FROM extensions
                                    JOIN extensionversions ON (extensionversions.extension=extensions.id)
                                    JOIN extensionroles_processchanges ON (extensionroles_processchanges.version=extensionversions.id)
                                   WHERE extensions.author=%s
                                     AND extensions.name=%s
                                     AND extensionroles_processchanges.uid=%s
                                     AND extensionroles_processchanges.script=%s
                                     AND extensionroles_processchanges.function=%s""",
                               (author.id, self.__extension_name, user.id, role.script, role.function))
            else:
                continue

            row = cursor.fetchone()
            if row:
                version_ids.add(row[0])
                installed_roles += 1
                role.installed = True
            else:
                role.installed = False

        if installed_roles == 0:
            manifest.status = "none"
        elif installed_roles < len(manifest.roles) or len(version_ids) != 1:
            manifest.status = "partial"
        else:
            manifest.status = "installed"

        return manifest

    @staticmethod
    def getUpdatedExtensions(db, user):
        cursor = db.cursor()
        cursor.execute("""SELECT DISTINCT users.name, users.fullname, extensions.name, extensionversions.name, extensionversions.sha1
                            FROM users
                            JOIN extensions ON (extensions.author=users.id)
                            JOIN extensionversions ON (extensionversions.extension=extensions.id)
                            JOIN extensionroles ON (extensionroles.version=extensionversions.id)
                           WHERE extensionroles.uid=%s
                             AND extensionversions.sha1 IS NOT NULL""",
                       (user.id,))

        updated = []
        for author_name, author_fullname, extension_name, version_name, sha1 in cursor:
            extension = Extension(author_name, extension_name)
            if extension.getCurrentSHA1(version_name) != sha1:
                updated.append((author_fullname, extension_name))
        return updated

def getExtensionPath(author_name, extension_name):
    return os.path.join(configuration.extensions.SEARCH_ROOT, author_name, "CriticExtensions", extension_name)

def getExtensionInstallPath(sha1):
    return os.path.join(configuration.extensions.INSTALL_DIR, sha1)

def findExtensions():
    extensions = []

    for user_directory in os.listdir(configuration.extensions.SEARCH_ROOT):
        try:
            for extension_directory in os.listdir(os.path.join(configuration.extensions.SEARCH_ROOT, user_directory, "CriticExtensions")):
                extension_path = os.path.join(configuration.extensions.SEARCH_ROOT, user_directory, "CriticExtensions", extension_directory)

                if os.path.isdir(extension_path) and os.access(extension_path, os.X_OK | os.R_OK):
                    manifest_path = os.path.join(extension_path, "MANIFEST")

                    if os.path.isfile(manifest_path) and os.access(manifest_path, os.R_OK):
                        extensions.append(Extension(user_directory, extension_directory))
        except OSError:
            pass

    return extensions

def loadManifest(extension_path):
    manifest = Manifest(extension_path)
    manifest.read()
    return manifest

def doInstallExtension(db, user, extension, version):
    extension_id = extension.getExtensionID(db, create=True)
    manifest = extension.readManifest(version)

    cursor = db.cursor()

    if version is None:
        sha1 = None
        cursor.execute("SELECT id FROM extensionversions WHERE extension=%s AND sha1 IS NULL", (extension_id,))
    else:
        sha1 = extension.prepareVersionSnapshot(version)
        cursor.execute("SELECT id FROM extensionversions WHERE extension=%s AND sha1=%s", (extension_id, sha1))

    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO extensionversions (extension, name, sha1) VALUES (%s, %s, %s) RETURNING id", (extension_id, version, sha1))
        row = cursor.fetchone()

    version_id = row[0]

    for role in manifest.roles:
        role.install(cursor, version_id, user)

def doUninstallExtension(db, user, extension):
    extension_id = extension.getExtensionID(db)

    if extension_id is None: return

    cursor = db.cursor()

    cursor.execute("""DELETE FROM extensionroles
                            USING extensions, extensionversions
                            WHERE extensions.id=%s
                              AND extensionversions.extension=extensions.id
                              AND extensionroles.version=extensionversions.id
                              AND extensionroles.uid=%s""",
                   (extension_id, user.id))

def installExtension(db, user, author_name, extension_name, version):
    doInstallExtension(db, user, Extension(author_name, extension_name), version)
    db.commit()

def uninstallExtension(db, user, author_name, extension_name, version):
    doUninstallExtension(db, user, Extension(author_name, extension_name))
    db.commit()

def reinstallExtension(db, user, author_name, extension_name, version):
    doUninstallExtension(db, user, Extension(author_name, extension_name))
    doInstallExtension(db, user, Extension(author_name, extension_name), version)
    db.commit()

RE_COLLAPSE_WS = re.compile("[ \n]+")

def getJSShellCommandLine(rlimit_cpu="5s", rlimit_rss="256m"):
    return [configuration.executables.JSSHELL,
            "--rlimit-cpu=%s" % rlimit_cpu,
            "--rlimit-rss=%s" % rlimit_rss,
            os.path.join(configuration.extensions.JS_LIBRARY_DIR, "critic-launcher.js")]

def getJSShellDataLine(extension_path, extension_id, user_id, role, script, fn, argv):
    return "%s\n" % json_encode({ "criticjs_path": os.path.join(configuration.extensions.JS_LIBRARY_DIR, "critic2.js"),
                                  "dbname": configuration.database.PARAMETERS["database"],
                                  "dbuser": configuration.database.PARAMETERS["user"],
                                  "git_path": configuration.executables.GIT,
                                  "repository_work_copy_path": os.path.join(configuration.paths.DATA_DIR, "temporary", "EXTENSIONS"),
                                  "is_development": configuration.base.IS_DEVELOPMENT,
                                  "extension_path": extension_path,
                                  "extension_id": extension_id,
                                  "user_id": user_id,
                                  "role": role,
                                  "script_path": script,
                                  "fn": fn,
                                  "argv": argv })

def executeProcessCommits(db, user, review, all_commits, old_head, new_head, output):
    produced_output = False
    cursor = db.cursor()

    cursor.execute("""SELECT extensions.id, extensions.author, extensions.name, extensionversions.sha1, roles.script, roles.function
                        FROM extensions
                        JOIN extensionversions ON (extensionversions.extension=extensions.id)
                        JOIN extensionroles_processcommits AS roles ON (roles.version=extensionversions.id)
                       WHERE uid=%s
                         AND filter IS NULL""", (user.id,))

    rows = cursor.fetchall()

    if rows:
        commitset = CommitSet(all_commits)

        assert old_head is None or old_head in commitset.getTails()
        assert new_head in commitset.getHeads()
        assert len(commitset.getHeads()) == 1

        tails = commitset.getFilteredTails(review.repository)
        if len(tails) == 1:
            tail = gitutils.Commit.fromSHA1(db, review.repository, tails.pop())
            changeset_id = changeset.utils.createChangeset(db, user, review.repository, from_commit=tail, to_commit=new_head)[0].id
            changeset_arg = "repository.getChangeset(%d)" % changeset_id
            db.commit()
        else:
            changeset_arg = "null"

        commits = "[%s]" % ",".join([("repository.getCommit(%d)" % commit.getId(db)) for commit in all_commits])

        data = { "review_id": review.id,
                 "changeset": changeset_arg,
                 "commits": commits }

        for extension_id, author_id, extension_name, sha1, script, function in rows:
            author = dbutils.User.fromId(db, author_id)

            if sha1 is None: extension_path = getExtensionPath(author.name, extension_name)
            else: extension_path = getExtensionInstallPath(sha1)

            data["function"] = jsify(function)
            argv = """

(function ()
 {
   var review = new critic.Review(%(review_id)d);
   var repository = review.repository;
   var changeset = %(changeset)s;
   var commitset = new critic.CommitSet(%(commits)s);

   return [review, changeset, commitset];
 })()

""" % data
            argv = RE_COLLAPSE_WS.sub(" ", argv.strip())

            jsshell = process(getJSShellCommandLine(), stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=extension_path)

            stdout, stderr = jsshell.communicate(getJSShellDataLine(extension_id, user.id, "ProcessCommits", script, function, argv))

            if stdout.strip() or stderr.strip() or jsshell.returncode != 0:
                header = "%s::%s()" % (script, function)

                print >>output, "\n[%s] %s\n[%s] %s" % (extension_name, header, extension_name, "=" * len(header))

                produced_output = True

                if stderr.strip() or jsshell.returncode != 0:
                    for line in stderr.strip().splitlines():
                        print >>output, "[%s:stderr] %s" % (extension_name, line)

                    if jsshell.returncode != 0:
                        if jsshell.returncode < 0:
                            if -jsshell.returncode == signal.SIGXCPU:
                                print >>output, "[%s] Extension error: time limit (5 CPU seconds) exceeded" % extension_name
                            else:
                                print >>output, "[%s] Extension error: terminated by signal %d\n" % (extension_name, -jsshell.returncode)
                        else:
                            print >>output, "[%s] Extension error: jsshell exited with status %d" % (extension_name, jsshell.returncode)
                else:
                    for line in stdout.splitlines():
                        print >>output, "[%s] %s" % (extension_name, line)

    return produced_output

def executeProcessChanges(db, user_id, batch_id, output):
    produced_output = False
    cursor = db.cursor()

    cursor.execute("SELECT review, uid FROM batches WHERE id=%s", (batch_id,))

    review_id, batch_user_id = cursor.fetchone()

    cursor.execute("""SELECT extensions.id, extensions.author, extensions.name, extensionversions.sha1, roles.id, roles.script, roles.function
                        FROM extensions
                        JOIN extensionversions ON (extensionversions.extension=extensions.id)
                        JOIN extensionroles_processchanges AS roles ON (roles.version=extensionversions.id)
                       WHERE uid=%s AND roles.skip < %s""", (user_id, batch_id))

    rows = cursor.fetchall()

    if rows:
        data = { "review_id": review_id,
                 "batch_id": batch_id }

        for extension_id, author_id, extension_name, sha1, role_id, script, function in rows:
            cursor.execute("INSERT INTO extensionprocessedbatches (batch, role) VALUES (%s, %s)", (batch_id, role_id))

            # Don't do further processing of own batches.
            if batch_user_id == user_id: continue

            author = dbutils.User.fromId(db, author_id)

            if sha1 is None: extension_path = getExtensionPath(author.name, extension_name)
            else: extension_path = getExtensionInstallPath(sha1)

            data["function"] = jsify(function)
            argv = "[(new critic.Review(%(review_id)d)).getBatch(%(batch_id)d)]" % data

            jsshell = process(getJSShellCommandLine(), stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=extension_path)

            stdout, stderr = jsshell.communicate(getJSShellDataLine(extension_id, user.id, "ProcessChanges", script, function, argv))

            if stdout.strip() or stderr.strip() or jsshell.returncode != 0:
                header = "%s::%s()" % (script, function)

                print >>output, "\n[%s] %s\n[%s] %s" % (extension_name, header, extension_name, "=" * len(header))

                produced_output = True

                if stderr.strip() or jsshell.returncode != 0:
                    for line in stderr.strip().splitlines():
                        print >>output, "[%s:stderr] %s" % (extension_name, line)

                    if jsshell.returncode != 0:
                        if jsshell.returncode < 0:
                            if -jsshell.returncode == signal.SIGXCPU:
                                print >>output, "[%s] Extension error: time limit (5 CPU seconds) exceeded" % extension_name
                            else:
                                print >>output, "[%s] Extension error: terminated by signal %d\n" % (extension_name, -jsshell.returncode)
                        else:
                            print >>output, "[%s] Extension error: jsshell exited with status %d" % (extension_name, jsshell.returncode)
                else:
                    for line in stdout.splitlines():
                        print >>output, "[%s] %s" % (extension_name, line)

        db.commit()

    return produced_output

def executePage(db, req, user):
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

            manifest = loadManifest(extension_path)

            for role in manifest.roles:
                if isinstance(role, PageRole) and role.regexp == regexp and role.script == script and role.function == function:
                    break
            else:
                continue

            data = { 'method': jsify(req.method),
                     'path': jsify(req.path),
                     'query': query,
                     'headers': headers,
                     'function': jsify(function) }
            argv = "[%(method)s, %(path)s, %(query)s, %(headers)s]" % data

            stdin_data = getJSShellDataLine(extension_path, extension_id, user.id, "Page", script, function, argv)

            if req.method == "POST":
                stdin_data += req.read()

            before = time.time()

            jsshell = process(getJSShellCommandLine(rlimit_cpu="60s"), stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=extension_path)

            stdout_data, stderr_data = jsshell.communicate(stdin_data)

            after = time.time()

            status = None
            headers = {}

            if stderr_data:
                req.setStatus(418, "I'm a teapot")
                return "Extension error:\n%s" % stderr_data

            if jsshell.returncode != 0:
                req.setStatus(418, "I'm a teapot")
                if jsshell.returncode < 0:
                    if -jsshell.returncode == signal.SIGXCPU:
                        return "Extension error: time limit (5 CPU seconds) exceeded\n"
                    else:
                        return "Extension error: terminated by signal %d\n" % -jsshell.returncode
                else:
                    return "Extension error: jsshell failed"

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

            if content_type.startswith("text/html"):
                stdout_data += "\n\n<!-- extension execution time: %.2f seconds -->\n" % (after - before)

            return stdout_data

    return False

class InjectError(Exception): pass

def processInject(stdout_data, links, injected):
    def processLine(commands, line):
        try:
            command, value = line.split(" ", 1)
        except ValueError:
            raise InjectError, "invalid line in output: line=%r" % line

        if command not in ("link", "script", "stylesheet", "preference"):
            raise InjectError, "invalid command: command=%r" % command

        try:
            value = json_decode(value.strip())
        except:
            raise InjectError, "value is not valid JSON: value=%r" % value
            return False

        def is_string(value):
            return isinstance(value, str) or isinstance(value, unicode)

        if command in ("script", "stylesheet") and not is_string(value):
            raise InjectError, "expected string value for %s command: value=%r" % (command, value)
            return False
        elif command == "link":
            if not isinstance(value, list) or len(value) != 2:
                raise InjectError, "expected array or length two as value for %s command: value=%r" % (command, value)
                return False
            elif not is_string(value[0]):
                raise InjectError, "expected string at array[0] for %s command: value=%r" % (command, value)
                return False
            elif not (is_string(value[1]) or value[1] is None):
                raise InjectError, "expected string or null at array[1] for %s command: value=%r" % (command, value)
                return False
        elif command == "preference":
            if path != "config":
                raise InjectError, "'preference' command only valid on config page"
                return False
            elif not isinstance(value, dict):
                raise InjectError, "expected dictionary as argument for %s command: value=%r" % (command, value)
                return False

            for name in ("url", "name", "type", "value", "default", "description"):
                if name not in value:
                    raise InjectError, "%r not in argument for %s command: value=%r" % (name, command, value)
                    return False

            preference_url = value["url"]
            preference_name = value["name"]
            preference_type = value["type"]
            preference_value = value["value"]
            preference_default = value["default"]
            preference_description = value["description"]

            if not is_string(preference_url):
                raise InjectError, "value['url'] is not a string for %s command: value=%r" % (command, value)
                return False
            elif not is_string(preference_name):
                raise InjectError, "value['name'] is not a string for %s command: value=%r" % (command, value)
                return False
            elif not is_string(preference_description):
                raise InjectError, "value['description'] is not a string for %s command: value=%r" % (command, value)
                return False

            if is_string(preference_type):
                if preference_type not in ("boolean", "integer", "string"):
                    raise InjectError, "value['type'] is not valid: value=%r" % (preference_type)
                    return False

                if preference_type == "boolean": type_check = lambda value: isinstance(value, bool)
                elif preference_type == "integer": type_check = lambda value: isinstance(value, int)
                else: type_check = is_string

                if not type_check(preference_value):
                    raise InjectError, "type of value['value'] incompatible with value['type']: type=%r, value=%r" % (preference_type, preference_value)
                    return False

                if not type_check(preference_default):
                    raise InjectError, "type of value['default'] incompatible with value['type']: type=%r, value=%r" % (preference_type, preference_default)
                    return False
            else:
                if not isinstance(preference_type, list):
                    raise InjectError, "value['type'] is not valid: value=%r" % (preference_type)
                    return False

                for index, choice in enumerate(preference_type):
                    if not isinstance(choice, dict) or "value" not in choice or "title" not in choice or not is_string(choice["value"]) or not is_string(choice["title"]):
                        raise InjectError, "value['type'][%d] is not valid: value=%r" % (index, choice)
                        return False

                choices = set([choice["value"] for choice in preference_type])
                if len(choices) != len(preference_type):
                    raise InjectError, "value['type'] is not valid: value=%r" % (command, preference_type)
                    return False

                if not is_string(preference_value) or preference_value not in choices:
                    raise InjectError, "type of value['value'] incompatible with value['type']: type=%r, value=%r" % (preference_type, preference_value)
                    return False

                if not is_string(preference_default) or preference_default not in choices:
                    raise InjectError, "type of value['default'] incompatible with value['type']: type=%r, value=%r" % (preference_type, preference_default)
                    return False

        commands.append((command, value))
        return True

    commands = []
    failed = False

    for line in stdout_data.splitlines():
        if line.strip():
            if not processLine(commands, line.strip()):
                failed = True
                break

    if not failed:
        preferences = None

        for command, value in commands:
            if command == "script":
                injected.setdefault("scripts", []).append(value)
            elif command == "stylesheet":
                injected.setdefault("stylesheets", []).append(value)
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

def executeInject(db, paths, args, user, document, links, injected, profiler=None):
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

            if sha1 is None: extension_path = os.path.join(configuration.extensions.SEARCH_ROOT, author.name, "CriticExtensions", extension_name)
            else: extension_path = os.path.join(configuration.extensions.INSTALL_DIR, sha1)

            manifest = loadManifest(extension_path)

            for role in manifest.roles:
                if isinstance(role, InjectRole) and role.regexp == regexp and role.script == script and role.function == function:
                    break
            else:
                continue

            data = { 'user_id': user.id, 'path': jsify(path), 'query': query, 'function': jsify(function) }
            argv = "[%(path)s, %(query)s]" % data

            stdin_data = getJSShellDataLine(extension_path, extension_id, user.id, "Inject", script, function, argv)

            jsshell = process(getJSShellCommandLine(rlimit_cpu="60s"), stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=extension_path)

            before = time.time()

            stdout_data, stderr_data = jsshell.communicate(stdin_data)
            returncode = jsshell.returncode

            after = time.time()

            if stderr_data:
                document.comment("\n\nExtension error:\n%s\n" % stderr_data)
                continue

            if returncode != 0:
                if returncode < 0:
                    if -returncode == signal.SIGXCPU:
                        document.comment("\n\nExtension error: time limit (5 CPU seconds) exceeded\n\n")
                    else:
                        document.comment("\n\nExtension error: terminated by signal %d\n\n" % -returncode)
                else:
                    document.comment("\n\nExtension error: jsshell exited with status %d\n\n" % returncode)
                continue

            commands = []

            def processLine(line):
                try:
                    command, value = line.split(" ", 1)
                except ValueError:
                    document.comment("\n\nExtension error: invalid line in output: line=%r\n\n" % line)
                    return False

                if command not in ("link", "script", "stylesheet", "preference"):
                    document.comment("\n\nExtension error: invalid command: command=%r\n\n" % command)
                    return False

                try:
                    value = json_decode(value.strip())
                except:
                    document.comment("\n\nExtension error: value is not valid JSON: value=%r\n\n" % value)
                    return False

                def is_string(value):
                    return isinstance(value, str) or isinstance(value, unicode)

                if command in ("script", "stylesheet") and not is_string(value):
                    document.comment("\n\nExtension error: expected string value for %s command: value=%r\n\n" % (command, value))
                    return False
                elif command == "link":
                    if not isinstance(value, list) or len(value) != 2:
                        document.comment("\n\nExtension error: expected array or length two as value for %s command: value=%r\n\n" % (command, value))
                        return False
                    elif not is_string(value[0]):
                        document.comment("\n\nExtension error: expected string at array[0] for %s command: value=%r\n\n" % (command, value))
                        return False
                    elif not (is_string(value[1]) or value[1] is None):
                        document.comment("\n\nExtension error: expected string or null at array[1] for %s command: value=%r\n\n" % (command, value))
                        return False
                elif command == "preference":
                    if path != "config":
                        document.comment("\n\nExtension error: 'preference' command only valid on config page\n\n")
                        return False
                    elif not isinstance(value, dict):
                        document.comment("\n\nExtension error: expected dictionary as argument for %s command: value=%r\n\n" % (command, value))
                        return False

                    for name in ("url", "name", "type", "value", "default", "description"):
                        if name not in value:
                            document.comment("\n\nExtension error: %r not in argument for %s command: value=%r\n\n" % (name, command, value))
                            return False

                    preference_url = value["url"]
                    preference_name = value["name"]
                    preference_type = value["type"]
                    preference_value = value["value"]
                    preference_default = value["default"]
                    preference_description = value["description"]

                    if not is_string(preference_url):
                        document.comment("\n\nExtension error: value['url'] is not a string for %s command: value=%r\n\n" % (command, value))
                        return False
                    elif not is_string(preference_name):
                        document.comment("\n\nExtension error: value['name'] is not a string for %s command: value=%r\n\n" % (command, value))
                        return False
                    elif not is_string(preference_description):
                        document.comment("\n\nExtension error: value['description'] is not a string for %s command: value=%r\n\n" % (command, value))
                        return False

                    if is_string(preference_type):
                        if preference_type not in ("boolean", "integer", "string"):
                            document.comment("\n\nExtension error: value['type'] is not valid: value=%r\n\n" % (preference_type))
                            return False

                        if preference_type == "boolean": type_check = lambda value: isinstance(value, bool)
                        elif preference_type == "integer": type_check = lambda value: isinstance(value, int)
                        else: type_check = is_string

                        if not type_check(preference_value):
                            document.comment("\n\nExtension error: type of value['value'] incompatible with value['type']: type=%r, value=%r\n\n" % (preference_type, preference_value))
                            return False

                        if not type_check(preference_default):
                            document.comment("\n\nExtension error: type of value['default'] incompatible with value['type']: type=%r, value=%r\n\n" % (preference_type, preference_default))
                            return False
                    else:
                        if not isinstance(preference_type, list):
                            document.comment("\n\nExtension error: value['type'] is not valid: value=%r\n\n" % (preference_type))
                            return False

                        for index, choice in enumerate(preference_type):
                            if not isinstance(choice, dict) or "value" not in choice or "title" not in choice or not is_string(choice["value"]) or not is_string(choice["title"]):
                                document.comment("\n\nExtension error: value['type'][%d] is not valid: value=%r\n\n" % (index, choice))
                                return False

                        choices = set([choice["value"] for choice in preference_type])
                        if len(choices) != len(preference_type):
                            document.comment("\n\nExtension error: value['type'] is not valid: value=%r\n\n" % (command, preference_type))
                            return False

                        if not is_string(preference_value) or preference_value not in choices:
                            document.comment("\n\nExtension error: type of value['value'] incompatible with value['type']: type=%r, value=%r\n\n" % (preference_type, preference_value))
                            return False

                        if not is_string(preference_default) or preference_default not in choices:
                            document.comment("\n\nExtension error: type of value['default'] incompatible with value['type']: type=%r, value=%r\n\n" % (preference_type, preference_default))
                            return False

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

            if profiler: profiler.check("inject: %s/%s" % (author.name, extension_name))

def getExtensionResource(req, db, user, path):
    cursor = db.cursor()

    extension_name, resource_path = path.split("/", 1)

    cursor.execute("""SELECT extensions.author, extensionversions.sha1
                        FROM extensions
                        JOIN extensionversions ON (extensionversions.extension=extensions.id)
                        JOIN extensionroles ON (extensionroles.version=extensionversions.id)
                       WHERE extensions.name=%s
                         AND extensionroles.uid=%s
                       LIMIT 1""", (extension_name, user.id))

    row = cursor.fetchone()
    if not row: return None, None

    author_id, sha1 = row

    if sha1 is None:
        author = dbutils.User.fromId(db, author_id)
        extension_path = getExtensionPath(author.name, extension_name)
    else:
        extension_path = getExtensionInstallPath(sha1)

    resource_path = os.path.join(extension_path, "resources", resource_path)

    def guessContentType(name):
        try:
            name, ext = name.split(".", 1)
            return configuration.mimetypes.MIMETYPES[ext]
        except:
            return "application/octet-stream"

    if os.path.isfile(resource_path) and os.access(resource_path, os.R_OK):
        return guessContentType(resource_path), open(resource_path).read()
    else:
        return None, None
