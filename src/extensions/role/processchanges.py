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

import signal

import configuration
import dbutils

from extensions import getExtensionPath, getExtensionInstallPath
from extensions.execute import executeProcess, ProcessTimeout, ProcessError
from extensions.manifest import Manifest, ManifestError, ProcessChangesRole

def execute(db, user_id, batch_id, output):
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
        for extension_id, author_id, extension_name, sha1, role_id, script, function in rows:
            cursor.execute("INSERT INTO extensionprocessedbatches (batch, role) VALUES (%s, %s)", (batch_id, role_id))

            # Don't do further processing of own batches.
            if batch_user_id == user_id: continue

            author = dbutils.User.fromId(db, author_id)

            if sha1 is None:
                extension_path = getExtensionPath(author.name, extension_name)
            else:
                extension_path = getExtensionInstallPath(sha1)

            class Error(Exception):
                pass

            def print_header():
                header = "%s::%s()" % (script, function)
                print >>output, "\n[%s] %s\n[%s] %s" % (extension_name, header, extension_name, "=" * len(header))

            try:
                try:
                    manifest = Manifest.load(extension_path)
                except ManifestError, error:
                    raise Error("Invalid MANIFEST:\n%s" % error.message)

                for role in manifest.roles:
                    if isinstance(role, ProcessChangesRole) and role.script == script and role.function == function:
                        break
                else:
                    continue

                argv = "[(new critic.Review(%d)).getBatch(%d)]" % (review_id, batch_id)

                try:
                    stdout_data = executeProcess(manifest, role, extension_id, user_id, argv, configuration.extensions.SHORT_TIMEOUT)
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

                if stdout_data.strip():
                    print_header()
                    for line in stdout_data.splitlines():
                        print >>output, "[%s] %s" % (extension_name, line)
            except Error, error:
                print_header()
                print >>output, "[%s] Extension error: %s" % (extension_name, error.message)

            db.commit()
