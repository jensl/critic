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

import sys
import os
import time
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import background.utils
import dbutils
import gitutils
import mailutils
import configuration

# Git (git-send-pack) appends a line suffix to its output.  This suffix depends
# on the $TERM value.  When $TERM is "dumb", the suffix is 8 spaces.  We strip
# this suffix if it's present.  (If we incorrectly strip 8 spaces not actually
# added by Git, it's not the end of the world.)
#
# See https://github.com/git/git/blob/master/sideband.c for details.
DUMB_SUFFIX = "        "

class BranchTracker(background.utils.BackgroundProcess):
    def __init__(self):
        super(BranchTracker, self).__init__(service=configuration.services.BRANCHTRACKER)

    def update(self, trackedbranch_id, repository_id, local_name, remote, remote_name, forced):
        repository = gitutils.Repository.fromId(self.db, repository_id)

        try:
            with repository.relaycopy("branchtracker") as relay:
                relay.run("remote", "add", "source", remote)

                current = None
                new = None
                tags = []

                if local_name == "*":
                    output = relay.run("fetch", "source", "refs/tags/*:refs/tags/*", include_stderr=True)
                    for line in output.splitlines():
                        if "[new tag]" in line:
                            tags.append(line.rsplit(" ", 1)[-1])
                else:
                    relay.run("fetch", "--quiet", "--no-tags", "source", "refs/heads/%s:refs/remotes/source/%s" % (remote_name, remote_name))
                    try:
                        current = repository.revparse("refs/heads/%s" % local_name)
                    except gitutils.GitReferenceError:
                        # It's okay if the local branch doesn't exist (yet).
                        pass
                    new = relay.run("rev-parse", "refs/remotes/source/%s" % remote_name).strip()

                if current != new or tags:
                    if local_name == "*":
                        refspecs = [("refs/tags/%s" % tag) for tag in tags]
                    else:
                        refspecs = ["refs/remotes/source/%s:refs/heads/%s"
                                    % (remote_name, local_name)]

                    returncode, stdout, stderr = relay.run(
                        "push", "--force", "origin", *refspecs,
                        env={ "CRITIC_FLAGS": "trackedbranch_id=%d" % trackedbranch_id,
                              "TERM": "dumb" },
                        check_errors=False)

                    stderr_lines = []
                    remote_lines = []

                    for line in stderr.splitlines():
                        if line.endswith(DUMB_SUFFIX):
                            line = line[:-len(DUMB_SUFFIX)]
                        stderr_lines.append(line)
                        if line.startswith("remote: "):
                            line = line[8:]
                            remote_lines.append(line)

                    if returncode == 0:
                        if local_name == "*":
                            for tag in tags:
                                self.info("  updated tag: %s" % tag)
                        elif current:
                            self.info("  updated branch: %s: %s..%s" % (local_name, current[:8], new[:8]))
                        else:
                            self.info("  created branch: %s: %s" % (local_name, new[:8]))

                        hook_output = ""

                        for line in remote_lines:
                            self.debug("  [hook] " + line)
                            hook_output += line + "\n"

                        if local_name != "*":
                            cursor = self.db.cursor()
                            cursor.execute("INSERT INTO trackedbranchlog (branch, from_sha1, to_sha1, hook_output, successful) VALUES (%s, %s, %s, %s, %s)",
                                           (trackedbranch_id, current if current else '0' * 40, new if new else '0' * 40, hook_output, True))
                            self.db.commit()
                    else:
                        if local_name == "*":
                            error = "update of tags from %s failed" % remote
                        else:
                            error = "update of branch %s from %s in %s failed" % (local_name, remote_name, remote)

                        hook_output = ""

                        for line in stderr_lines:
                            error += "\n    " + line

                        for line in remote_lines:
                            hook_output += line + "\n"

                        self.error(error)

                        cursor = self.db.cursor()

                        if local_name != "*":
                            cursor.execute("""INSERT INTO trackedbranchlog (branch, from_sha1, to_sha1, hook_output, successful)
                                                   VALUES (%s, %s, %s, %s, %s)""",
                                           (trackedbranch_id, current, new, hook_output, False))
                            self.db.commit()

                        cursor.execute("SELECT uid FROM trackedbranchusers WHERE branch=%s", (trackedbranch_id,))
                        recipients = [dbutils.User.fromId(self.db, user_id) for (user_id,) in cursor]

                        if local_name == "*":
                            mailutils.sendMessage(recipients, "%s: update of tags from %s stopped!" % (repository.name, remote),
                                                  """\
The automatic update of tags in
  %s:%s
from the remote
  %s
failed, and has been disabled.  Manual intervention is required to resume the
automatic updating.

Output from Critic's git hook
-----------------------------

%s""" % (configuration.base.HOSTNAME, repository.path, remote, hook_output))
                        else:
                            mailutils.sendMessage(recipients, "%s: update from %s in %s stopped!" % (local_name, remote_name, remote),
                                                  """\
The automatic update of the branch '%s' in
  %s:%s
from the branch '%s' in
  %s
failed, and has been disabled.  Manual intervention is required to resume the
automatic updating.

Output from Critic's git hook
-----------------------------

%s""" % (local_name, configuration.base.HOSTNAME, repository.path, remote_name, remote, hook_output))

                        # Disable the tracking.
                        return False
                else:
                    self.debug("  fetched %s in %s; no changes" % (remote_name, remote))

            # Everything went well; keep the tracking enabled.
            return True
        except:
            exception = traceback.format_exc()

            if local_name == "*":
                error = "  update of tags from %s failed" % remote
            else:
                error = "  update of branch %s from %s in %s failed" % (local_name, remote_name, remote)

            for line in exception.splitlines():
                error += "\n    " + line

            self.error(error)

            # The expected failure (in case of diverged branches, or review branch
            # irregularities) is a failed "git push" and is handled above.  This is
            # an unexpected failure, so might be intermittent.  Leave the tracking
            # enabled and spam the system administrator(s).
            return True

    def run(self):
        self.db = dbutils.Database.forSystem()

        while not self.terminated:
            self.interrupted = False

            cursor = self.db.cursor()
            cursor.execute("""SELECT id, repository, local_name, remote, remote_name, forced
                                FROM trackedbranches
                               WHERE NOT disabled
                                 AND (next IS NULL OR next < NOW())
                            ORDER BY next ASC NULLS FIRST""")
            rows = cursor.fetchall()

            for trackedbranch_id, repository_id, local_name, remote, remote_name, forced in rows:
                if local_name == "*":
                    self.info("checking tags in %s" % remote)
                else:
                    self.info("checking %s in %s" % (remote_name, remote))

                cursor.execute("""UPDATE trackedbranches
                                     SET previous=NOW(),
                                         next=NOW() + delay,
                                         updating=TRUE
                                   WHERE id=%s""",
                               (trackedbranch_id,))

                self.db.commit()

                if self.update(trackedbranch_id, repository_id, local_name, remote, remote_name, forced):
                    cursor.execute("""UPDATE trackedbranches
                                         SET updating=FALSE
                                       WHERE id=%s""",
                                   (trackedbranch_id,))
                    cursor.execute("""SELECT next::text
                                        FROM trackedbranches
                                       WHERE id=%s""",
                                   (trackedbranch_id,))
                    self.info("  next scheduled update at %s" % cursor.fetchone())
                else:
                    cursor.execute("""UPDATE trackedbranches
                                         SET updating=FALSE,
                                             disabled=TRUE
                                       WHERE id=%s""",
                                   (trackedbranch_id,))
                    self.info("  tracking disabled")

                self.db.commit()

                if self.terminated: break

            cursor.execute("""SELECT 1
                                FROM trackedbranches
                               WHERE NOT disabled
                                 AND next IS NULL""")

            if not cursor.fetchone():
                maintenance_delay = self.run_maintenance()

                if maintenance_delay is None:
                    maintenance_delay = 3600

                cursor.execute("""SELECT COUNT(*), EXTRACT('epoch' FROM (MIN(next) - NOW()))
                                    FROM trackedbranches
                                   WHERE NOT disabled""")

                enabled_branches, update_delay = cursor.fetchone()

                if not enabled_branches:
                    self.info("nothing to do")
                    update_delay = 3600
                else:
                    update_delay = max(0, int(update_delay))

                delay = min(maintenance_delay, update_delay)

                if delay:
                    self.signal_idle_state()

                    self.debug("sleeping %d seconds" % delay)

                    gitutils.Repository.forEach(self.db, lambda db, repository: repository.stopBatch())

                    self.db.commit()

                    before = time.time()
                    time.sleep(delay)
                    if self.interrupted:
                        self.debug("sleep interrupted after %.2f seconds" % (time.time() - before))

            self.db.commit()

def start_service():
    tracker = BranchTracker()
    return tracker.start()

background.utils.call("branchtracker", start_service)
