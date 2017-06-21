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

import sys
import os
import os.path
import time
import traceback
import StringIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "..")))

import configuration
import dbutils
import gitutils
import textutils
import background.utils
import dbutils
import auth

try:
    from customization.email import getUserEmailAddress
except ImportError:
    def getUserEmailAddress(_username):
        return None

def getUser(db, user_name):
    if user_name == configuration.base.SYSTEM_USER_NAME:
        return dbutils.User.makeSystem()
    try:
        return dbutils.User.fromName(db, user_name)
    except dbutils.NoSuchUser:
        if configuration.base.AUTHENTICATION_MODE == "host":
            email = getUserEmailAddress(user_name)
            return dbutils.User.create(
                db, user_name, user_name, email, email_verified=None)
        raise

ALLOWED_PATHS = frozenset(["refs/heads/",
                           "refs/tags/",
                           "refs/temporary/",
                           "refs/keepalive/",
                           "refs/roots/"])

# Specifically due to restrictions on the 'name' column in the database table
# 'pendingrefupdates' (the 'tags' and 'branches' tables have similar limits),
# but also: insanely long ref names make no sense.
MAXIMUM_REF_NAME_LENGTH = 256

def reflow(text):
    """Reflow text to a line length suitable for Git hook output"""
    return textutils.reflow(text, line_length=80 - len("remote: "))

def validate_ref_name(ref):
    ref_name = ref["ref_name"]
    if len(ref_name) > MAXIMUM_REF_NAME_LENGTH:
        return "longer than %d characters" % MAXIMUM_REF_NAME_LENGTH
    if not ref_name.startswith("refs/"):
        return "must start with refs/"
    for allowed_path in ALLOWED_PATHS:
        if ref_name.startswith(allowed_path):
            break
    else:
        parts = ref_name.split("/")
        if len(parts) > 2:
            prefix = "/".join(parts[:2]) + "/"
            return "invalid prefix: %s" % prefix
        else:
            return "invalid name"
    if (ref_name.startswith("refs/temporary/") or
        ref_name.startswith("refs/keepalive/")):
        # Ref name must be refs/*/<sha1>.
        sha1 = ref_name[len("refs/keepalive/"):]
        if ref["new_sha1"] != sha1:
            return "malformed temporary or keepalive ref"

def validate_ref_update(db, user, repository, ref_name):
    cursor = db.readonly_cursor()
    cursor.execute("""SELECT id, updater, state
                        FROM pendingrefupdates
                       WHERE repository=%s
                         AND name=%s
                         AND state NOT IN ('finished', 'failed')""",
                   (repository.id, ref_name))
    row = cursor.fetchone()
    if row:
        pendingrefupdate_id, updater_id, state = row
        if state == 'finished':
            with db.updating_cursor("pendingrefupdates") as cursor:
                cursor.execute("""DELETE
                                    FROM pendingrefupdates
                                   WHERE id=%s""",
                               (pendingrefupdate_id,))
            return
        updater = dbutils.User.fromId(db, updater_id)
        if updater == user:
            who = "you"
        else:
            who = "%s <%s>" % (updater.fullname, updater.email)
        return (("An update of %s by %s is already pending.  "
                 "Please wait a few seconds, or up to a minute, for "
                 "the pending update to be processed or time out.")
                % (ref_name, who))

def validate_ref_creation(db, repository, ref_name):
    cursor = db.readonly_cursor()

    def isref(ref_name):
        if repository.isref(ref_name):
            return True
        if ref_name.startswith("refs/heads/"):
            # Check the database too.  This is necessary to consider branches
            # that have been archived, but also to detect cases where the Git
            # repository and the database have become out of sync.
            branch_name = ref_name[len("refs/heads/"):]
            cursor.execute("""SELECT 1
                                FROM branches
                               WHERE repository=%s
                                 AND name=%s""",
                           (repository.id, branch_name))
            if cursor.fetchone():
                return True

    # Check if there's an existing ref whose full path occurs as a parent
    # directory in the created ref's full path.
    components = ref_name.split("/")
    for count in range(3, len(components)):
        existing_ref_name = "/".join(components[:count])
        if isref(existing_ref_name):
            return "%s: conflicts with ref: %s" % (ref_name, existing_ref_name)

    # Check if the created ref's full path occurs as a parent directory in the
    # full path of an existing ref.
    output = repository.run(
        "for-each-ref", "--count=1", "--format=%(refname)", ref_name + "/")
    existing_ref_name = output.strip()
    if existing_ref_name:
        return "%s: conflicts with ref: %s" % (ref_name, existing_ref_name)
    # Again, check the database too.  Same reasons as above.
    cursor.execute("""SELECT name
                        FROM branches
                       WHERE repository=%s
                         AND name LIKE %s
                       LIMIT 1""",
                   (repository.id, ref_name + "/%"))
    row = cursor.fetchone()
    if row:
        existing_ref_name, = row
        return "%s: conflicts with ref: %s" % (ref_name, existing_ref_name)

def validate_commits(db, repository, refs):
    added_sha1s = list(set(ref["new_sha1"] for ref in refs
                           if ref["new_sha1"] != "0" * 40))

    # List added root commits.
    output = repository.run(
        *(["rev-list", "--max-parents=0"] + added_sha1s + ["--not", "--all"]))
    added_roots = output.strip().splitlines()
    if not added_roots:
        return

    # Typically, adding new root commits is disallowed.  There are two
    # exceptions:
    # - There are no roots in the repository currently.
    # - A single ref named refs/roots/<sha1> is being created, where <sha1> is
    #   the SHA-1 of the added root commit.
    if len(refs) == 1 == len(added_roots) and added_roots[0] in added_sha1s:
        if refs[0]["ref_name"] == "refs/roots/" + added_roots[0]:
            return

    try:
        output = repository.run(
            "rev-list", "--count", "--max-parents=0", "--all")
    except gitutils.GitCommandError:
        # 'git rev-list --all' fails in an empty repository with no refs in it,
        # since it was given no refs on the command line.
        return
    else:
        if output.strip() == "0":
            return

    if len(added_roots) == 1:
        return "new root commit added: %s" % added_roots[0]
    else:
        return "%d new root commits added:\n  " + "\n  ".join(added_roots)

def find_tracked_branch(db, repository, branch_name):
    cursor = db.readonly_cursor()
    cursor.execute("""SELECT id, remote, remote_name
                        FROM trackedbranches
                       WHERE repository=%s
                         AND local_name=%s
                         AND NOT disabled""",
                   (repository.id, branch_name))
    row = cursor.fetchone()
    if not row:
        return None, None, None
    trackedbranch_id, remote, remote_name = row
    return trackedbranch_id, remote, remote_name

def validate_branch_creation(db, user, repository, flags,
                             branch_name, new_sha1):
    # Check if a branch with this name already exists in the database.  If one
    # does, then either the database and the repository are out of sync, or the
    # branch is one that has been archived.
    branch = dbutils.Branch.fromName(
        db, repository, branch_name, load_review=True)

    if branch and branch.archived:
        # This is an archived branch.  Since archived branches are actually
        # deleted from the repository, it's expected that Git thinks we're
        # creating a new branch.
        message = ("The branch '%s' in this repository has been archived, "
                   "meaning it has been hidden from view to reduce the number "
                   "of visible refs in this repository.") % branch_name

        if branch.review:
            message += ("\n\n"
                        "To continue working on this branch, you need to first "
                        "reopen the review that is associated with the branch. "
                        " You can do this from the review's front-page:\n\n")
            message += branch.review.getURL(db, user, indent=2)
        elif new_sha1 == branch.head.sha1:
            # Non-review branches can be resurrected by pushing their (supposed)
            # current value.
            return
        else:
            message += (("\n\n"
                         "To continue working on this branch, you need to "
                         "first resurrect it.  You can do this by first "
                         "recreating it with its current value:\n\n"
                         "  git push critic %s:refs/heads/%s")
                        % (branch.head.sha1, branch_name))

        return ("conflicts with archived branch", message)

    if not branch:
        if dbutils.Branch.isReviewBranch(db, repository, branch_name):
            if not user.getPreference(db, "review.createViaPush"):
                return ("would submit new review",
                        ("To submit new reviews directly via push, you first "
                         "need to enable the review.createViaPush setting:\n\n"
                         "  %s")
                        % user.getCriticURLs(
                            db, "/config?highlight=review.createViaPush"))

def validate_branch_deletion(db, user, repository, flags, branch_name):
    # We don't allow deletion of review branches.
    if dbutils.Branch.isReviewBranch(db, repository, branch_name):
        return "%s is a review branch!" % branch_name

    # We also don't allow deletion (or other updates) of tracked branches.
    trackedbranch_id, remote, remote_name = find_tracked_branch(
        db, repository, branch_name)
    if trackedbranch_id:
        return ("tracking branch",
                ("The branch %s in this repository tracks %s in %s, and should "
                 "not be deleted in this repository.")
                % (branch_name, remote_name, remote))

def validate_branch_update(db, user, repository, flags,
                           branch_name, old_sha1, new_sha1):
    # We don't allow manual updates of tracked branches.  However, if |flags|
    # contains a tracked branch id, and it matches the branch being updated,
    # this is the branch tracker pushing, which of course is fine.
    trackedbranch_id, remote, remote_name = find_tracked_branch(
        db, repository, branch_name)
    if remote and trackedbranch_id != flags.get("trackedbranch_id"):
        return ("tracking branch",
                ("The branch %s in this repository tracks %s in %s, and should "
                 "not be updated directly in this repository.")
                % (branch_name, remote_name, remote))

    branch = dbutils.Branch.fromName(db, repository, branch_name)

    if branch is None:
        # Branch missing from the database.  Pretend it is being created.
        return validate_branch_creation(db, user, repository, flags,
                                        branch_name, new_sha1)

    review = dbutils.Review.fromBranch(db, branch)

    if review:
        return review.validateBranchUpdate(db, user, old_sha1, new_sha1, flags)

    return branch.validateUpdate(db, user, old_sha1, new_sha1, flags)

def perform_custom_checks(repository, ref):
    try:
        from customization.githook import Reject, update
    except ImportError as error:
        return

    previous_stdout = sys.stdout
    sys.stdout = StringIO.StringIO()

    old_value = None if ref["old_sha1"] == 40 * '0' else ref["old_sha1"]
    new_value = None if ref["new_sha1"] == 40 * '0' else ref["new_sha1"]

    try:
        update(repository.path, ref["ref_name"], old_value, new_value)
        return False, sys.stdout.getvalue().strip()
    except Reject as rejection:
        return True, str(rejection)
    finally:
        sys.stdout = previous_stdout

def format_error(name, category, error):
    if isinstance(error, basestring):
        title, message = error, None
    else:
        title, message = error

    if not isinstance(name, basestring):
        name = "\n".join(name)

    if category:
        result = "%s rejected:\n  %s:\n    %s" % (name, category, title)
    else:
        result = "%s rejected:\n  %s" % (name, title)

    if message:
        result += "\n\n" + reflow(message)

    return result.strip() + "\n\n"

class GitHookSlave(background.utils.PeerServer.ChildProcess):
    def __init__(self, server, client, user, repository, refs, ids):
        super(GitHookSlave, self).__init__(
            server, [sys.executable, "-m", "background.githook", "--slave"],
            chunked=True)
        self.client = client
        self.write(textutils.json_encode({ "user_id": user.id,
                                           "repository_id": repository.id,
                                           "refs": refs,
                                           "ids": ids }))
        self.close()

    def handle_input(self, _file, data, closed):
        for line in data.splitlines():
            self.server.debug("slave output%s: %s" % (" (closed)" if closed else "", line))
            data = textutils.json_decode(line)
            if "error" in data:
                self.server.error(data["error"])
            self.client.respond(output=data.get("output"), close=False)
        if closed:
            self.client.close()

class GitHookClient(background.utils.PeerServer.SocketPeer):
    def __init__(self, server, socket):
        # Use lenient=True since the hook script may be killed if the user
        # aborts the "git push" command.  This is not an error situation (from
        # our perspective) so just silently ignore the resulting socket errors.
        super(GitHookClient, self).__init__(server, socket, lenient=True)

    def respond(self, output=None, accept=False, reject=False, close=True):
        data = {}
        if output is not None:
            if not isinstance(output, basestring):
                output = "".join(output)
            data["output"] = output
        if accept:
            data["accept"] = True
        if reject:
            data["reject"] = True
        self.write(textutils.json_encode(data) + "\n")
        if close:
            self.close()

    def handle_input(self, _file, data):
        self.server.debug("input: %s" % data)

        data = textutils.json_decode(data)

        user_name = data["user_name"]
        repository_name = data["repository_name"]
        flags = {}

        if user_name == configuration.base.SYSTEM_USER_NAME:
            # Use the REMOTE_USER environment variable (from the environment
            # with which the git hook ran) if present.
            #
            # We use it only if the actual user was the Critic system user,
            # meaning the push was performed by the branch tracker service,
            # the web front-end (for instance via 'git http-backend') or an
            # extension.
            #
            # We also look at the CRITIC_FLAGS environment variable, also only
            # if the actual user was the Critic system user.
            user_name = data["environ"].get("REMOTE_USER")
            flags = textutils.json_decode(
                data["environ"].get("CRITIC_FLAGS", "{}"))

        db = self.server.db
        db.refresh()

        cursor = db.readonly_cursor()
        user = (getUser(db, user_name)
                if user_name else
                dbutils.User.makeSystem())

        with gitutils.Repository.fromName(db, repository_name) as repository:
            if data["hook"] == "pre-receive":
                self.handle_pre_receive(
                    db, user, repository, flags, data["refs"])
            elif data["hook"] == "post-receive":
                self.handle_post_receive(
                    db, user, repository, flags, data["refs"])
            else:
                self.respond(reject=True)

        # Make sure we're not in an active transaction.
        db.rollback()

    def handle_pre_receive(self, db, user, repository, flags, refs):
        cursor = db.readonly_cursor()

        # First check that all updated refs have valid names.  We only allow
        # refs under some paths under refs/ (see ALLOWED_PREFIXES above.)
        invalid_ref_names = []
        for ref in refs:
            error = validate_ref_name(ref)
            if error:
                invalid_ref_names.append(format_error(
                    ref["ref_name"], None, error))
        if invalid_ref_names:
            self.respond(output=invalid_ref_names, reject=True)
            return

        # Next check if there's already a pending update for any of the updated
        # refs.
        pending_updates = []
        for ref in refs:
            ref_name = ref["ref_name"]
            pending_update = validate_ref_update(db, user, repository, ref_name)
            if pending_update:
                pending_updates.append(format_error(
                    ref_name, None, ("has pending update", pending_update)))
        if pending_updates:
            self.respond(output=pending_updates, reject=True)
            return

        # Next check that would-be created refs can actually be created, or
        # if they conflict with existing refs.
        conflicting_refs = []
        for ref in refs:
            if ref["old_sha1"] == "0" * 40:
                ref_name = ref["ref_name"]
                conflicting_ref_name = validate_ref_creation(
                    db, repository, ref_name)
                if conflicting_ref_name:
                    conflicting_refs.append(format_error(
                        ref_name, "conflicts with existing ref",
                        conflicting_ref_name))
        if conflicting_refs:
            self.respond(output=conflicting_refs, reject=True)
            return

        # Next check that the updates add only allowed commits to the
        # repository.  (It's too late, really; the commits will already be in
        # the repository by now, but if we reject ref updates, they'll stay
        # unreferenced an be garbage collected soon.)
        disallowed_commits = validate_commits(db, repository, refs)
        if disallowed_commits:
            error = disallowed_commits, ("New root commits can only be pushed "
                                         "to empty repositories, or by "
                                         "pushing only a ref named "
                                         "'refs/roots/SHA1' where 'SHA1' is "
                                         "the full SHA-1 of the root commit in "
                                         "in question.")
            self.respond(
                output=format_error([ref["ref_name"] for ref in refs],
                                    None, error),
                reject=True)
            return

        # Next perform validations of the actual branch updates.
        invalid_branch_updates = []
        for ref in refs:
            if ref["ref_name"].startswith("refs/heads/"):
                branch_name = ref["ref_name"][len("refs/heads/"):]
                if ref["old_sha1"] == "0" * 40:
                    category = "invalid branch creation"
                    error = validate_branch_creation(
                        db, user, repository, flags, branch_name,
                        ref["new_sha1"])
                elif ref["new_sha1"] == "0" * 40:
                    category = "invalid branch deletion"
                    error = validate_branch_deletion(
                        db, user, repository, flags, branch_name)
                else:
                    category = "invalid branch update"
                    error = validate_branch_update(
                        db, user, repository, flags, branch_name,
                        ref["old_sha1"], ref["new_sha1"])
                if error:
                    invalid_branch_updates.append(format_error(
                        branch_name, category, error))
        if invalid_branch_updates:
            self.respond(output=invalid_branch_updates, reject=True)
            return

        # Finally, perform custom checks, if there are any.
        custom_output = []
        custom_rejected = False
        for ref in refs:
            self.server.debug("custom checking: " + ref["ref_name"])
            result = perform_custom_checks(repository, ref)
            self.server.debug("custom result: %r" % (result,))
            if result:
                ref_rejected, output = result
                if ref_rejected:
                    custom_rejected = True
                if output:
                    custom_output.append(output)
        if custom_output:
            custom_output.append("\n")
        if custom_rejected:
            self.respond(output=custom_output, reject=True)
            return
        elif custom_output:
            self.respond(output=custom_output, close=False)

        flags = textutils.json_encode(flags)

        # Finally, insert pending update records into the database and wake
        # the branch updater background service up to take note of it.  (It
        # won't do anything right now since it's a preliminary update; it
        # will set a timeout and go back to sleep.)
        with db.updating_cursor("pendingrefupdates") as cursor:
            cursor.executemany(
                """INSERT INTO pendingrefupdates (repository, name,
                                                  old_sha1, new_sha1,
                                                  updater, flags)
                        VALUES (%s, %s,
                                %s, %s,
                                %s, %s)""",
                [(repository.id, ref["ref_name"],
                  ref["old_sha1"], ref["new_sha1"],
                  user.id, flags)
                 for ref in refs])
        background.utils.wakeup(configuration.services.BRANCHUPDATER)

        self.respond(accept=True)

    def handle_post_receive(self, db, user, repository, flags, refs):
        # This is intentionally quite lenient.  In extreme cases the pending ref
        # update could have been deleted already, and we have nothing
        # particularly meaningful to report about that; it's entirely possible
        # everything went alright, just very, very slowly.

        pendingrefupdate_refs = []
        pendingrefupdate_ids = []

        cursor = db.readonly_cursor()

        for ref in refs:
            cursor.execute(
                """SELECT id
                     FROM pendingrefupdates
                    WHERE repository=%s
                      AND name=%s
                      AND old_sha1=%s
                      AND new_sha1=%s
                      AND (updater=%s OR updater IS NULL AND %s)""",
                (repository.id, ref["ref_name"],
                 ref["old_sha1"], ref["new_sha1"],
                 user.id, user.isSystem()))
            row = cursor.fetchone()
            if row:
                (pendingrefupdate_id,) = row
                pendingrefupdate_refs.append(ref)
                pendingrefupdate_ids.append(pendingrefupdate_id)
            else:
                self.server.warning(
                    "Pending ref missing: %s in %s (%s..%s)"
                    % (ref["ref_name"], repository.name,
                       ref["old_sha1"][:8], ref["new_sha1"][:8]))

        if not pendingrefupdate_refs:
            # Nothing for the slave process to wait for or handle.
            self.respond()
            return

        background.utils.wakeup(configuration.services.BRANCHUPDATER)

        self.server.info("Starting slave process...")

        self.server.add_peer(GitHookSlave(
            self.server, self, user, repository,
            pendingrefupdate_refs, pendingrefupdate_ids))

class GitHookServer(background.utils.PeerServer):
    def __init__(self):
        super(GitHookServer, self).__init__(service=configuration.services.GITHOOK)
        self.db = dbutils.Database()

    def startup(self):
        super(GitHookServer, self).startup()
        os.chmod(configuration.services.GITHOOK["address"], 0770)

    def handle_peer(self, peersocket, peeraddress):
        return GitHookClient(self, peersocket)

def start_service():
    server = GitHookServer()
    return server.start()

def run_slave0():
    data = textutils.json_decode(sys.stdin.read())

    def write(text):
        # Insert an empty line between each block of output emitted, unless a
        # block ends with "...".
        if not text.endswith("..."):
            text += "\n"
        data = textutils.json_encode({ "output": text + "\n" })
        sys.stdout.write(data + "\n")
        sys.stdout.flush()

    user_id = data["user_id"]
    repository_id = data["repository_id"]

    class Update(object):
        def __init__(self, update_id, ref_name):
            self.update_id = update_id
            self.ref_name = ref_name
            self.status = None
            self.output_seen = -1

    updates = {
        update_id: Update(update_id, ref_name)
        for update_id, ref_name in zip(data["ids"], data["refs"])
    }

    db = dbutils.Database.forUser()

    user = (dbutils.User.fromId(db, user_id)
            if user_id is not None else
            dbutils.User.makeSystem())
    db.setUser(user)

    repository = gitutils.Repository.fromId(db, repository_id)

    start = time.time()
    deadline = start + user.getPreference(
        db, "repository.postReceiveTimeout", repository=repository)

    cursor = db.readonly_cursor()
    output_per_ref = {}
    send_is_waiting = True

    if len(updates) > 1:
        output_format = "%(ref_name)s:\n\n%(output)s"
    else:
        output_format = "%(output)s"

    sleep_time = 0.1
    slept_time = 0

    while time.time() < deadline:
        time.sleep(sleep_time)

        slept_time += sleep_time
        sleep_time = min(sleep_time * 2, 1)

        db.refresh()

        cursor.execute(
            """SELECT pendingrefupdate, id, output
                 FROM pendingrefupdateoutputs
                WHERE pendingrefupdate=ANY (%s)
             ORDER BY pendingrefupdate, id""",
            (updates.keys(),))

        for update_id, output_id, output in cursor:
            update = updates[update_id]
            if output_id <= update.output_seen:
                # Already seen.
                continue
            write(output_format % { "ref_name": update.ref_name,
                                    "output": output.rstrip() })
            update.output_seen = output_id
            # Skip the "is waiting text" if we've received any output.  It's
            # technically still valid/relevant, but it'll just be confusing to
            # intermingle it with "regular" output.
            send_is_waiting = False

        cursor.execute(
            """SELECT COUNT(*)
                 FROM pendingrefupdates
                WHERE id=ANY (%s)
                  AND state NOT IN ('finished', 'failed')""",
            (updates.keys(),))

        remaining, = cursor.fetchone()

        if remaining == 0:
            break

        if send_is_waiting and slept_time >= 1:
            message = (("Waiting for the update%(plural)s to be processed. "
                        "It is safe to stop waiting (e.g. by pressing ctrl-c); "
                        "the update%(plural)s will still be processed.")
                       % { "plural": ("s" if len(updates) > 1 else "") })
            write(reflow(message))
            send_is_waiting = False
    else:
        # Something appears to have timed out.

        cursor.execute(
            """SELECT id
                 FROM pendingrefupdates
                WHERE id=ANY (%s)
                  AND state NOT IN ('finished', 'failed')""",
            (updates.keys(),))

        timed_out = [update_id for (update_id,) in cursor]

        if timed_out:
            output = "Timed out waiting for Critic to process the update!"

            for update_id in timed_out:
                update = updates[update_id]
                write(output_format % { "ref_name": update.ref_name,
                                        "output": output })

            message = (("Note that the update%(plural)s will continue to be "
                        "processed in the background, and will complete "
                        "eventually, unless something catastrophic has gone "
                        "wrong.")
                       % { "plural": ("s" if len(updates) > 1 else "") })
            write(reflow(message))

            with db.updating_cursor("pendingrefupdates") as cursor:
                cursor.execute(
                    """UPDATE pendingrefupdates
                          SET abandoned=TRUE
                        WHERE id=ANY (%s)""",
                    (timed_out,))

    cursor = db.readonly_cursor()
    cursor.execute(
        """SELECT id
             FROM pendingrefupdates
            WHERE id=ANY (%s)
              AND state='failed'""",
        (updates.keys(),))

    update_ids = [update_id for update_id, in cursor]

    for update_id in update_ids:
        # Revert failed ref update.
        cursor.execute("""SELECT name, old_sha1, new_sha1, branchupdate
                            FROM pendingrefupdates
                           WHERE id=%s""",
                       (update_id,))

        ref_name, old_sha1, new_sha1, update_id = cursor.fetchone()

        if new_sha1 != "0" * 40:
            # Make sure the new commits are preserved, to enable debugging.
            repository.keepalive(new_sha1)

        if old_sha1 == "0" * 40:
            # Ref was created: delete it, so that it can be created again.
            repository.deleteref(ref_name, new_sha1)
            restored_to = "oblivion"
        elif new_sha1 == "0" * 40:
            # Ref was deleted: recreate it.
            repository.createref(ref_name, old_sha1)
            restored_to = old_sha1[:8]
        else:
            # Ref was updated: reset it back to the old value.
            repository.updateref(ref_name, old_sha1, new_sha1)
            restored_to = old_sha1[:8]

        write("%s: failed => reset back to: %s" % (ref_name, restored_to))

        try:
            if update_id is not None:
                dbutils.Branch.revertUpdate(db, update_id)
        except Exception:
            write(traceback.format_exc())

    # Delete all finished updates.  Skip ones we just marked as abandoned above,
    # since the user will not have seen the result.
    #
    # If they are finished or failed now, there was a race between the
    # branch/review updater services and us.  No big deal.  Abandoned and
    # finished/failed updates are cleaned up by the branch updater service and
    # the user is notified about any significant results (such as failure.)
    with db.updating_cursor("pendingrefupdates") as cursor:
       cursor.execute(
           """DELETE FROM pendingrefupdates
                    WHERE id=ANY (%s)
                      AND state IN ('finished', 'failed')
                      AND NOT abandoned""",
           (updates.keys(),))

def run_slave():
    try:
        run_slave0()
    except:
        sys.stdout.write(textutils.json_encode({
            "error": traceback.format_exc()
        }) + "\n")
        sys.stdout.flush()

if "--slave" in sys.argv:
    background.utils.call("githook", run_slave)
else:
    background.utils.call("githook", start_service)
