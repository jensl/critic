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

import configuration
import gitutils

import log.commitset
import changeset.utils

from communicate import ProcessTimeout, ProcessError

from extensions import getExtensionInstallPath
from extensions.extension import Extension
from extensions.execute import executeProcess
from extensions.manifest import Manifest, ManifestError, ProcessCommitsRole

def execute(db, user, review, all_commits, old_head, new_head, output):
    cursor = db.cursor()

    installs = Extension.getInstalls(db, user)

    data = None

    for extension_id, version_id, version_sha1, is_universal in installs:
        handlers = []

        if version_id is not None:
            cursor.execute("""SELECT script, function
                                FROM extensionroles
                                JOIN extensionprocesscommitsroles ON (role=id)
                               WHERE version=%s
                            ORDER BY id ASC""",
                           (version_id,))

            handlers.extend(cursor)

            if not handlers:
                continue

            extension_path = getExtensionInstallPath(version_sha1)
            manifest = Manifest.load(extension_path)
        else:
            extension = Extension.fromId(db, extension_id)
            manifest = Manifest.load(extension.getPath())

            for role in manifest.roles:
                if isinstance(role, ProcessCommitsRole):
                    handlers.append((role.script, role.function))

            if not handlers:
                continue

        if data is None:
            commitset = log.commitset.CommitSet(all_commits)

            assert old_head is None or old_head in commitset.getTails()
            assert new_head in commitset.getHeads()
            assert len(commitset.getHeads()) == 1

            tails = commitset.getFilteredTails(review.repository)
            if len(tails) == 1:
                tail = gitutils.Commit.fromSHA1(db, review.repository, tails.pop())
                changeset_id = changeset.utils.createChangeset(
                    db, user, review.repository, from_commit=tail, to_commit=new_head)[0].id
                changeset_arg = "repository.getChangeset(%d)" % changeset_id
            else:
                changeset_arg = "null"

            commits_arg = "[%s]" % ",".join(
                [("repository.getCommit(%d)" % commit.getId(db))
                 for commit in all_commits])

            data = { "review_id": review.id,
                     "changeset": changeset_arg,
                     "commits": commits_arg }

        for script, function in handlers:
            class Error(Exception):
                pass

            def print_header():
                header = "%s::%s()" % (script, function)
                print >>output, ("\n[%s] %s\n[%s] %s"
                                 % (extension.getName(), header,
                                    extension.getName(), "=" * len(header)))

            try:
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
                    stdout_data = executeProcess(
                        manifest, "processcommits", script, function, extension_id, user.id,
                        argv, configuration.extensions.SHORT_TIMEOUT)
                except ProcessTimeout:
                    raise Error("Timeout after %d seconds." % configuration.extensions.SHORT_TIMEOUT)
                except ProcessError as error:
                    if error.returncode < 0:
                        raise Error("Process terminated by signal %d." % -error.returncode)
                    else:
                        raise Error("Process returned %d.\n%s" % (error.returncode, error.stderr))

                if stdout_data.strip():
                    print_header()
                    for line in stdout_data.splitlines():
                        print >>output, "[%s] %s" % (extension.getName(), line)
            except Error as error:
                print_header()
                print >>output, "[%s] Extension error: %s" % (extension.getName(), error.message)
