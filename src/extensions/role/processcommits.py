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
import signal

import configuration
import dbutils
import gitutils

import log.commitset
import changeset.utils

from extensions import getExtensionPath, getExtensionInstallPath
from extensions.execute import executeProcess, ProcessTimeout, ProcessError
from extensions.manifest import Manifest, ManifestError, ProcessCommitsRole

def execute(db, user, review, all_commits, old_head, new_head, output):
    cursor = db.cursor()
    cursor.execute("""SELECT extensions.id, extensions.author, extensions.name, extensionversions.sha1, roles.script, roles.function
                        FROM extensions
                        JOIN extensionversions ON (extensionversions.extension=extensions.id)
                        JOIN extensionroles_processcommits AS roles ON (roles.version=extensionversions.id)
                       WHERE uid=%s
                         AND filter IS NULL""", (user.id,))

    rows = cursor.fetchall()

    if rows:
        commitset = log.commitset.CommitSet(all_commits)

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
                    if isinstance(role, ProcessCommitsRole) and role.script == script and role.function == function:
                        break
                else:
                    continue

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
                argv = re.sub("[ \n]+", " ", argv.strip())

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

                if stdout_data.strip():
                    print_header()
                    for line in stdout_data.splitlines():
                        print >>output, "[%s] %s" % (extension_name, line)
            except Error, error:
                print_header()
                print >>output, "[%s] Extension error: %s" % (extension_name, error.message)
