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
import os
import signal
import traceback

import configuration
import dbutils
import gitutils
import mailutils
import htmlutils

from extensions.extension import Extension, ExtensionError
from extensions.manifest import Manifest, ManifestError, FilterHookRole
from extensions.execute import ProcessException, ProcessFailure, executeProcess

def signalExtensionTasksService():
    try:
        with open(configuration.services.EXTENSIONTASKS["pidfile_path"]) as pidfile:
            pid = int(pidfile.read().strip())
        os.kill(pid, signal.SIGHUP)
    except Exception:
        # Print traceback to stderr.  Might end up in web server's error log,
        # where it has a chance to be noticed.
        traceback.print_exc()

def listFilterHooks(db, user):
    cursor = db.cursor()

    installs = Extension.getInstalls(db, user)
    filterhooks = []

    for extension_id, version_id, version_sha1, is_universal in installs:
        if version_id is not None:
            cursor.execute("""SELECT 1
                                FROM extensionroles
                                JOIN extensionfilterhookroles ON (role=id)
                               WHERE version=%s""",
                           (version_id,))

            if not cursor.fetchone():
                continue

            extension = Extension.fromId(db, extension_id)
            manifest = extension.getManifest(sha1=version_sha1)
        else:
            try:
                extension = Extension.fromId(db, extension_id)
            except ExtensionError:
                # If the author/hosting user no longer exists, or the extension
                # directory no longer exists or is inaccessible, ignore the
                # extension.
                continue

            try:
                manifest = Manifest.load(extension.getPath())
            except ManifestError:
                # If the MANIFEST is missing or invalid, we can't know whether
                # the extension has any filter hook roles, so assume it doesn't
                # and ignore it.
                continue

            if not any(isinstance(role, FilterHookRole)
                       for role in manifest.roles):
                continue

        filterhooks.append((extension, manifest, sorted(
                    (role for role in manifest.roles
                     if isinstance(role, FilterHookRole)),
                    key=lambda role: role.title)))

    return sorted(filterhooks,
                  key=lambda extension_manifest_roles: extension_manifest_roles[0].getKey())

def getFilterHookRole(db, filter_id):
    cursor = db.cursor()

    cursor.execute("""SELECT extension, uid, name
                        FROM extensionhookfilters
                       WHERE id=%s""",
                   (filter_id,))

    extension_id, user_id, filterhook_name = cursor.fetchone()

    extension = Extension.fromId(db, extension_id)
    user = dbutils.User.fromId(db, user_id)

    installed_sha1, _ = extension.getInstalledVersion(db, user)

    if installed_sha1 is False:
        return

    manifest = extension.getManifest(sha1=installed_sha1)

    for role in manifest.roles:
        if isinstance(role, FilterHookRole) and role.name == filterhook_name:
            return role

def queueFilterHookEvent(db, filter_id, review, user, commits, file_ids):
    cursor = db.readonly_cursor()
    cursor.execute("""SELECT data
                        FROM extensionhookfilters
                       WHERE id=%s""",
                   (filter_id,))

    data, = cursor.fetchone()

    with db.updating_cursor("extensionfilterhookevents",
                            "extensionfilterhookcommits",
                            "extensionfilterhookfiles") as cursor:
        cursor.execute("""INSERT INTO extensionfilterhookevents
                                        (filter, review, uid, data)
                               VALUES (%s, %s, %s, %s)
                            RETURNING id""",
                       (filter_id, review.id, user.id, data))

        event_id, = cursor.fetchone()

        cursor.executemany("""INSERT INTO extensionfilterhookcommits
                                            (event, commit)
                                   VALUES (%s, %s)""",
                           [(event_id, commit.getId(db)) for commit in commits])

        cursor.executemany("""INSERT INTO extensionfilterhookfiles
                                            (event, file)
                                   VALUES (%s, %s)""",
                           [(event_id, file_id) for file_id in file_ids])

        def transactionCallback(event):
            if event == "commit":
                signalExtensionTasksService()

        db.registerTransactionCallback(transactionCallback)

def processFilterHookEvent(db, event_id, logfn):
    cursor = db.cursor()

    cursor.execute("""SELECT filters.extension, filters.uid, filters.path,
                             filters.name, events.review, events.uid, events.data
                        FROM extensionfilterhookevents AS events
                        JOIN extensionhookfilters AS filters ON (filters.id=events.filter)
                       WHERE events.id=%s""",
                   (event_id,))

    # Note:
    # - filter_user_id / filter_user represent the user whose filter was
    #   triggered.
    # - user_id /user represent the user that added commits and thereby
    #   triggered the filter.

    (extension_id, filter_user_id, filter_path,
     filterhook_name, review_id, user_id, filter_data) = cursor.fetchone()

    extension = Extension.fromId(db, extension_id)
    filter_user = dbutils.User.fromId(db, filter_user_id)

    installed_sha1, _ = extension.getInstalledVersion(db, filter_user)

    if installed_sha1 is False:
        # Invalid event (user doesn't have extension installed); do nothing.
        # The event will be deleted by the caller.
        return

    manifest = extension.getManifest(sha1=installed_sha1)

    for role in manifest.roles:
        if isinstance(role, FilterHookRole) and role.name == filterhook_name:
            break
    else:
        # Invalid event (installed version of extension doesn't have the named
        # filter hook role); do nothing.  The event will be deleted by the
        # caller.
        return

    cursor.execute("""SELECT commit
                        FROM extensionfilterhookcommits
                       WHERE event=%s""",
                   (event_id,))
    commit_ids = [commit_id for (commit_id,) in cursor]

    cursor.execute("""SELECT file
                        FROM extensionfilterhookfiles
                       WHERE event=%s""",
                   (event_id,))
    file_ids = [file_id for (file_id,) in cursor]

    argv = """

(function () {
   var review = new critic.Review(%(review_id)d);
   var user = new critic.User(%(user_id)d);
   var repository = review.repository;
   var commits = new critic.CommitSet(
     %(commit_ids)r.map(
       function (commit_id) {
         return repository.getCommit(commit_id);
       }));
   var files = %(file_ids)r.map(
     function (file_id) {
       return critic.File.find(file_id);
     });
   return [%(filter_data)s, review, user, commits, files];
 })()

""" % { "filter_data": htmlutils.jsify(filter_data),
        "review_id": review_id,
        "user_id": user_id,
        "commit_ids": commit_ids,
        "file_ids": file_ids }

    argv = re.sub("[ \n]+", " ", argv.strip())

    logfn("argv=%r" % argv)
    logfn("script=%r" % role.script)
    logfn("function=%r" % role.function)

    try:
        executeProcess(
            db, manifest, "filterhook", role.script, role.function, extension_id,
            filter_user_id, argv, configuration.extensions.LONG_TIMEOUT)
    except ProcessException as error:
        review = dbutils.Review.fromId(db, review_id)

        recipients = {filter_user}

        author = extension.getAuthor(db)
        if author is None:
            recipients.update(dbutils.User.withRole(db, "administrator"))
        else:
            recipients.add(author)

        body = """\
An error occurred while processing an extension hook filter event!

Filter details:

  Extension:   %(extension.title)s
  Filter hook: %(role.title)s
  Repository:  %(repository.name)s
  Path:        %(filter.path)s
  Data:        %(filter.data)s

Event details:

  Review:  r/%(review.id)d "%(review.summary)s"
  Commits: %(commits)s

Error details:

  Error:  %(error.message)s
  Output:%(error.output)s

-- critic"""

        commits = (gitutils.Commit.fromId(db, review.repository, commit_id)
                   for commit_id in commit_ids)
        commits_text = "\n           ".join(
            ('%s "%s"' % (commit.sha1[:8], commit.niceSummary())
             for commit in commits))

        if isinstance(error, ProcessFailure):
            error_output = "\n\n    " + "\n    ".join(error.stderr.splitlines())
        else:
            error_output = " %s" % error.message

        body = body % { "extension.title": extension.getTitle(db),
                        "role.title": role.title,
                        "repository.name": review.repository.name,
                        "filter.path": filter_path,
                        "filter.data": htmlutils.jsify(filter_data),
                        "review.id": review.id,
                        "review.summary": review.summary,
                        "commits": commits_text,
                        "error.message": error.message,
                        "error.output": error_output }

        mailutils.sendMessage(
            recipients=list(recipients),
            subject="Failed: " + role.title,
            body=body)
