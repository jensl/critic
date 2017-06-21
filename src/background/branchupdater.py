# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import datetime
import time
import traceback

import configuration
import api
import dbutils
import gitutils
import background.utils
import textutils

class BranchUpdater(background.utils.SleeperProcess):
    def __init__(self):
        service = configuration.services.BRANCHUPDATER
        super(BranchUpdater, self).__init__(service)
        self.preliminary_timeout = service.get("PRELIMINARY_TIMEOUT", 30)

    def wakeup(self):
        db = api.critic.startSession(for_system=True).database

        next_timeout = 3600
        update_reviews = False

        now = datetime.datetime.now()

        try:
            cursor = db.readonly_cursor()
            cursor.execute("""SELECT id, updater, repository, name,
                                     old_sha1, new_sha1, flags, state,
                                     started_at
                                FROM pendingrefupdates
                               WHERE state='preliminary'""")

            for (pendingrefupdate_id, user_id, repository_id,
                 ref_name, old_sha1, new_sha1, flags, state,
                 started_at) in cursor:
                duration = (now - started_at).total_seconds()
                user = (dbutils.User.fromId(db, user_id)
                        if user_id is not None else
                        dbutils.User.makeSystem())
                flags = textutils.json_decode(flags or "{}")

                with gitutils.Repository.fromId(db, repository_id) as repository:
                    try:
                        current_sha1 = repository.revparse(ref_name)
                    except gitutils.GitReferenceError:
                        current_sha1 = "0" * 40

                    if current_sha1 == new_sha1:
                        # The update has been performed by Git, so go ahead and
                        # process it.
                        if self.handle_update(
                                db, pendingrefupdate_id, user, repository,
                                ref_name, old_sha1, new_sha1, flags, state):
                            # Process review updates (since this was a review
                            # branch.)
                            update_reviews = True
                    elif duration >= self.preliminary_timeout:
                        # The update has timed out.  Probably the git push was
                        # aborted before it updated the ref, or Git simply
                        # failed/refused to go through with the update.
                        self.handle_preliminary_timeout(
                            db, pendingrefupdate_id, user, repository,
                            ref_name, old_sha1, new_sha1, current_sha1)
                    else:
                        # Make sure we wake up to time the update out.
                        next_timeout = min(next_timeout, max(
                            1, self.preliminary_timeout - duration))

            cursor.execute("""SELECT id, repository, name, old_sha1, new_sha1
                                FROM pendingrefupdates
                               WHERE state='failed'""")

            for (pendingrefupdate_id, repository_id, ref_name,
                 old_sha1, new_sha1) in cursor:
                pass
        finally:
            db.close()

        if update_reviews:
            background.utils.wakeup(configuration.services.REVIEWUPDATER)

        return next_timeout

    def handle_preliminary_timeout(self, db, pendingrefupdate_id, user,
                                   repository, ref_name, old_sha1, new_sha1,
                                   current_sha1):
        if current_sha1 != old_sha1:
            # Weirdness: We're waiting for a ref to change in one way, and it
            # ends up changing in a different way.  The pre-recieve hook should
            # block all updates of the ref while there is a pending update, so
            # this should not have happened.
            self.error(
                ("Unexpected ref update in repository '%(repository)s':\n"
                 "  %(ref_name)s changed  %(old_sha1)s..%(current_sha1)s,\n"
                 "  %(padding)s  expected %(old_sha1)s..%(new_sha1)s\n")
                % { "repository": repository.name,
                    "ref_name": ref_name,
                    "old_sha1": old_sha1[:8],
                    "current_sha1": current_sha1[:8],
                    "new_sha1": new_sha1[:8] })
        else:
            self.info("Update timed out: %s in %s (%s..%s)"
                      % (ref_name, repository.name,
                         old_sha1[:8], new_sha1[:8]))

        # Forget about the update.
        with db.updating_cursor("pendingrefupdates") as cursor:
            cursor.execute("""DELETE FROM pendingrefupdates
                                    WHERE id=%s""",
                           (pendingrefupdate_id,))

    def handle_update(self, db, pendingrefupdate_id, user, repository,
                      ref_name, old_sha1, new_sha1, flags, state):
        self.debug("Processing update: %s (%s..%s) ..."
                   % (ref_name, old_sha1[:8], new_sha1[:8]))

        is_review_branch = False
        error = None

        if old_sha1 == "0" * 40:
            action = "creating"
        elif new_sha1 == "0" * 40:
            action = "deleting"
        else:
            action = "updating"

        try:
            if action != "deleting":
                repository.processCommits(db, new_sha1)

            if ref_name.startswith("refs/heads/"):
                branch_name = ref_name[len("refs/heads/"):]
                is_review_branch = dbutils.Branch.isReviewBranch(
                    db, repository, branch_name)

                if action == "creating":
                    commit = gitutils.Commit.fromSHA1(db, repository, new_sha1)
                    if is_review_branch:
                        dbutils.Review.create(db, user, branch_name, commit,
                                              pendingrefupdate_id)
                    else:
                        dbutils.Branch.create(db, user, branch_name, commit,
                                              pendingrefupdate_id)
                    self.debug("  created")
                elif action == "deleting":
                    branch = dbutils.Branch.fromName(
                        db, repository, branch_name)
                    commit = gitutils.Commit.fromSHA1(db, repository, old_sha1)
                    branch.delete(db, user, commit, pendingrefupdate_id)
                    self.debug("  deleted")
                else:
                    branch = dbutils.Branch.fromName(
                        db, repository, branch_name)
                    from_commit = gitutils.Commit.fromSHA1(
                        db, repository, old_sha1)
                    to_commit = gitutils.Commit.fromSHA1(
                        db, repository, new_sha1)
                    branch.update(db, user, from_commit, to_commit, flags,
                                  pendingrefupdate_id)
                    is_review_branch = branch.is_review_branch
                    self.debug("  updated")
            elif ref_name.startswith("refs/tags/"):
                tag_name = ref_name[len("refs/tags/"):]

                if action == "creating":
                    repository.createTag(db, tag_name, new_sha1)
                elif action == "deleting":
                    repository.deleteTag(db, tag_name)
                else:
                    repository.updateTag(db, tag_name, old_sha1, new_sha1)

            self.info("Processed update: %s in %s (%s..%s)"
                       % (ref_name, repository.name,
                          old_sha1[:8], new_sha1[:8]))
        except Exception:
            error = traceback.format_exc()

            gitutils.emitGitHookOutput(
                db, pendingrefupdate_id,
                # FIXME: Refine this error message.
                output="An error occurred while %s %s." % (action, ref_name),
                error=error)

            self.exception("Update failed: %s (%s..%s)"
                           % (ref_name, old_sha1[:8], new_sha1[:8]))

        if error:
            next_state = 'failed'
        elif is_review_branch:
            # This is a review branch, so we'll let the reviewupdater service
            # set the pending ref update's state to 'finished'.
            next_state = 'processed'
        else:
            next_state = 'finished'

        with db.updating_cursor("pendingrefupdates") as cursor:
            cursor.execute(
                """UPDATE pendingrefupdates
                      SET state=%s
                    WHERE id=%s""",
                (next_state, pendingrefupdate_id))

        return is_review_branch

def start_service():
    branch_updater = BranchUpdater()
    return branch_updater.start()

background.utils.call("branchupdater", start_service)
