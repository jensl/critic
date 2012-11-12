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

from dbutils import *
import gitutils
import time
import re
from htmlutils import htmlify, jsify, tabify, Document
from profiling import Profiler, formatDBProfiling
from utf8utils import convertUTF8
import itertools
import traceback
import sys
import os
import resource as resource_module
import cStringIO
import sys
import gc

try: from json import dumps as json_encode, loads as json_decode
except: from cjson import encode as json_encode, decode as json_decode

import request
import dbutils
import changeset.text
import changeset.html
import changeset.utils
import review.utils as review_utils
import review.comment as review_comment
import review.html as review_html
import review.filters as review_filters
import log.html as log_html
import log.commitset as log_commitset
import diff
import mailutils
import configuration

import operation.createcomment
import operation.createreview
import operation.manipulatecomment
import operation.manipulatereview
import operation.manipulatefilters
import operation.manipulateuser
import operation.manipulateassignments
import operation.fetchlines
import operation.markfiles
import operation.draftchanges
import operation.blame
import operation.trackedbranch
import operation.rebasereview
import operation.recipientfilter
import operation.editresource
import operation.autocompletedata
import operation.servicemanager
import operation.addrepository
import operation.news

import page.utils
import page.createreview
import page.branches
import page.showcomment
import page.showcommit
import page.showreview
import page.showreviewlog
import page.showbatch
import page.showbranch
import page.showtree
import page.showfile
import page.config
import page.dashboard
import page.home
import page.managereviewers
import page.filterchanges
import page.tutorial
import page.news
import page.editresource
import page.statistics
import page.confirmmerge
import page.addrepository
import page.checkbranch
import page.search
import page.repositories
import page.services

try:
    from customization.email import getUserEmailAddress
except ImportError:
    def getUserEmailAddress(username):
        return None

if configuration.extensions.ENABLED:
    RE_EXTENSION_RESOURCE = re.compile("^extension-resource/([a-z0-9][-._a-z0-9]+(?:/[a-z0-9][-._a-z0-9]+)+)$", re.IGNORECASE)

YesOrNo = page.utils.YesOrNo

from operation import OperationResult, OperationError

from traceback import format_exc

def generateEmpty(target):
    pass

def generateHeader(target, generate_right=generateEmpty):
    page.utils.generateHeader(target, generate_right)

def reviewFromArgument(db, argument):
    try:
        return dbutils.Review.fromId(db, int(argument))
    except:
        branch = dbutils.Branch.fromName(db, str(argument))
        if not branch: return None
        return dbutils.Review.fromBranch(db, branch)

def download(req, db, user):
    sha1 = req.getParameter("sha1")
    repository = gitutils.Repository.fromParameter(db, req.getParameter("repository", user.getPreference(db, "defaultRepository")))

    # etag = "\"critic.%s\"" % sha1

    # if req.headers_in.has_key("If-None-Match"):
    #     if etag == req.headers_in["If-None-Match"]:
    #         return apache.HTTP_NOT_MODIFIED

    match = re.search("\\.([a-z]+)", req.path)
    if match:
        req.setContentType(configuration.mimetypes.MIMETYPES.get(match.group(1), "application/octet-stream"))
    else:
        req.setContentType("application/octet-stream")

    # req.headers_out["ETag"] = etag

    return repository.fetch(sha1).data

def watchreview(req, db, user):
    review_id = req.getParameter("review", filter=int)
    user_name = req.getParameter("user")

    cursor = db.cursor()

    user = dbutils.User.fromName(db, user_name)

    cursor.execute("SELECT 1 FROM reviewusers WHERE review=%s AND uid=%s", (review_id, user.id))

    if not cursor.fetchone():
        cursor.execute("INSERT INTO reviewusers (review, uid, type) VALUES (%s, %s, 'manual')", (review_id, user.id))

        cursor.execute("SELECT uid, include FROM reviewrecipientfilters WHERE review=%s AND uid IN (0, %s)", (review_id, user.id))

        default_include = True
        user_include = None

        for user_id, include in cursor:
            if user_id == 0: default_include = include
            else: user_include = include

        if not default_include and user_include is None:
            cursor.execute("INSERT INTO reviewrecipientfilters (review, uid, include) VALUES (%s, %s, true)", (review_id, user.id))

        db.commit()

    return "ok"

def unwatchreview(req, db, user):
    review_id = req.getParameter("review", filter=int)
    user_name = req.getParameter("user")

    cursor = db.cursor()

    user = dbutils.User.fromName(db, user_name)

    cursor.execute("SELECT 1 FROM fullreviewuserfiles WHERE review=%s AND assignee=%s", (review_id, user.id))

    if cursor.fetchone():
        return "error:isreviewer"

    cursor.execute("DELETE FROM reviewusers WHERE review=%s AND uid=%s", (review_id, user.id))
    db.commit()

    return "ok"

def queryparentfilters(req, db, user):
    review_id = req.getParameter("review", filter=int)
    review = dbutils.Review.fromId(db, review_id)

    new_reviewers, new_watchers = review_utils.queryParentFilters(db, user, review)

    return "ok\n[ %s ]\n[ %s ]" % (", ".join([dbutils.User.fromId(db, user_id).getJSConstructor() for user_id in new_reviewers]),
                                   ", ".join([dbutils.User.fromId(db, user_id).getJSConstructor() for user_id in new_watchers]))

def applyparentfilters(req, db, user):
    review_id = req.getParameter("review", filter=int)
    review = dbutils.Review.fromId(db, review_id)
    review_utils.applyParentFilters(db, user, review)

    return "ok"

def setfullname(req, db, user):
    fullname = req.getParameter("fullname")

    cursor = db.cursor()
    cursor.execute("UPDATE users SET fullname=%s WHERE id=%s", (fullname, user.id))

    db.commit()

    return "ok"

def addfilter(req, db, user):
    cursor = db.cursor()

    repository_id = req.getParameter("repository", filter=int)
    filter_type = req.getParameter("type")
    filter_path = req.getParameter("path")
    filter_delegate = req.getParameter("delegate", "")
    force = req.getParameter("force", "no") == "yes"

    repository = gitutils.Repository.fromId(db, repository_id)

    if filter_delegate:
        invalid_users = []
        for delegate_name in map(str.strip, filter_delegate.split(',')):
            if dbutils.User.fromName(db, delegate_name) is None:
                invalid_users.append(delegate_name)
        if invalid_users: return "error:invalid-users:%s" % ','.join(invalid_users)

    if filter_path == '/':
        directory_id, file_id = 0, 0
    elif filter_path[-1] == '/':
        directory_id, file_id = find_directory(db, path=filter_path[:-1]), 0
    else:
        if not force and is_directory(db, filter_path): return "error:directory"
        else: directory_id, file_id = find_directory_file(db, filter_path)

    if directory_id:
        specificity = len(explode_path(db, directory_id=directory_id))
        if file_id: specificity += 1
    else:
        specificity = 0

    cursor.execute("INSERT INTO filters (uid, repository, directory, file, specificity, type, delegate) VALUES (%s, %s, %s, %s, %s, %s, %s)", [user.id, repository.id, directory_id, file_id, specificity, filter_type, ','.join(map(str.strip, filter_delegate.split(',')))])
    user.setPreference(db, "email.activated", True)

    db.commit()

    return "ok:directory=%d,file=%d" % (directory_id, file_id)

def deletefilter(req, db, user):
    cursor = db.cursor()

    repository_id = req.getParameter("repository", filter=int)
    directory_id = req.getParameter("directory", filter=int)
    file_id = req.getParameter("file", filter=int)

    cursor.execute("DELETE FROM filters WHERE uid=%s AND repository=%s AND directory=%s AND file=%s", (user.id, repository_id, directory_id, file_id))

    db.commit()

    return "ok"

def reapplyfilters(req, db, user):
    cursor1 = db.cursor()
    cursor2 = db.cursor()
    cursor3 = db.cursor()

    user = dbutils.User.fromName(db, req.getParameter("user", req.user))
    repository = gitutils.Repository.fromParameter(db, req.getParameter("repository", ""))

    if repository is None:
        cursor1.execute("""SELECT reviews.id, applyfilters, applyparentfilters, branches.repository FROM reviews JOIN branches ON (reviews.branch=branches.id) WHERE reviews.state!='closed'""")
    else:
        cursor1.execute("""SELECT reviews.id, applyfilters, applyparentfilters, branches.repository FROM reviews JOIN branches ON (reviews.branch=branches.id) WHERE reviews.state!='closed' AND branches.repository=%s""", (repository.id,))

    repositories = {}

    assign_changes = {}
    watch_reviews = set()

    reviews_with_filters = 0
    reviews_without_filters = 0

    own_commit = {}

    for review_id, applyfilters ,applyparentfilters, repository_id in cursor1:
        if repository_id not in repositories:
            repositories[repository_id] = gitutils.Repository.fromId(db, repository_id)
        repository = repositories[repository_id]

        filters = review_filters.Filters()
        filters.load(db, review=review_filters.Filters.Review(review_id, applyfilters, applyparentfilters, repository), user=user)

        if filters.hasFilters():
            reviews_with_filters += 1

            cursor2.execute("""SELECT changesets.id, changesets.child, reviewfiles.file, reviewfiles.id
                                 FROM changesets
                                 JOIN reviewfiles ON (reviewfiles.changeset=changesets.id)
                      LEFT OUTER JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id
                                                      AND reviewuserfiles.uid=%s)
                                WHERE reviewfiles.review=%s
                                  AND reviewuserfiles.uid IS NULL""",
                            (user.id, review_id))

            for changeset_id, commit_id, file_id, review_file_id in cursor2:
                users = filters.listUsers(db, file_id)

                if user.id in users:
                    if commit_id not in own_commit:
                        cursor3.execute("""SELECT uid
                                             FROM usergitemails
                                             JOIN gitusers USING (email)
                                             JOIN commits ON (commits.author_gituser=gitusers.id)
                                            WHERE commits.id=%s""",
                                        (commit_id,))
                        own_commit[commit_id] = cursor3.fetchone()[0] == user.id

                    if not own_commit[commit_id]:
                        if users[user.id][0] == 'reviewer':
                            assign_changes.setdefault(review_id, set()).add((file_id, review_file_id))
                        else:
                            watch_reviews.add(review_id)
        else:
            reviews_without_filters += 1

    new_reviews = set()

    for review_id in itertools.chain(assign_changes, watch_reviews):
        cursor1.execute("SELECT 1 FROM reviewusers WHERE review=%s AND uid=%s", (review_id, user.id))
        if not cursor1.fetchone(): new_reviews.add(review_id)

    cursor1.executemany("INSERT INTO reviewusers (review, uid) VALUES (%s, %s)", [(review_id, user.id) for review_id in new_reviews])

    reviewuserfiles_values = []

    for file_ids in assign_changes.values():
        reviewuserfiles_values.extend([(review_file_id, user.id) for file_id, review_file_id in file_ids])

    cursor1.executemany("INSERT INTO reviewuserfiles (file, uid) VALUES (%s, %s)", reviewuserfiles_values)

    result = ""

    for review_id in sorted(assign_changes.keys()):
        review = dbutils.Review.fromId(db, review_id, load_commits=False)
        file_ids = assign_changes[review_id]

        if review.state == 'open':
            result += "review,%s:%d:%s\n" % ("new" if review_id in new_reviews else "old", review.id, review.summary)

            paths = [describe_file(db, file_id) for file_id, review_file_id in file_ids]

            for path in diff.File.eliminateCommonPrefixes(sorted(paths), text=True):
                result += "  " + path + "\n"

    for review_id in sorted(watch_reviews & new_reviews):
       review = dbutils.Review.fromId(db, review_id, load_commits=False)

       if review.state == 'open':
           result += "watch:%d:%s\n" % (review.id, review.summary)

    db.commit()

    if not result:
        result = "nothing\n"

    return result

def savesettings(req, db, user):
    if user.isAnonymous():
        return "ok"

    data = req.read()
    values = [line.strip().split("=", 1) for line in data.splitlines() if line.strip()]

    cursor = db.cursor()

    integers = []
    strings = []

    for item, value in values:
        cursor.execute("SELECT type FROM preferences WHERE item=%s", [item])

        row = cursor.fetchone()
        if row:
            type = row[0]
            if type == "boolean":
                value = int(bool(int(value)))
                integers.append((user.id, item, value))
            elif type == "integer":
                value = int(value)
                integers.append((user.id, item, value))
            elif type == "string":
                strings.append((user.id, item, value))

    cursor.executemany("DELETE FROM userpreferences WHERE uid=%s AND item=%s", [(user.id, item[1]) for item in integers])
    cursor.executemany("DELETE FROM userpreferences WHERE uid=%s AND item=%s", [(user.id, item[1]) for item in strings])

    cursor.executemany("INSERT INTO userpreferences (uid, item, integer) VALUES (%s, %s, %s)", integers)
    cursor.executemany("INSERT INTO userpreferences (uid, item, string) VALUES (%s, %s, %s)", strings)

    db.commit()

    return "ok"

def showfilters(req, db, user):
    user = dbutils.User.fromName(db, req.getParameter("user", req.user))
    path = req.getParameter("path")
    repository = gitutils.Repository.fromParameter(db, req.getParameter("repository", user.getPreference(db, "defaultRepository")))

    path = path.rstrip("/")

    if is_directory(db, path):
        directory_id = find_directory(db, path=path)
        show_path = path + "/"

        cursor = db.cursor()
        cursor.execute("SELECT name FROM files WHERE directory=%s ORDER BY id ASC LIMIT 1", (directory_id,))

        row = cursor.fetchone()
        if row: path += "/" + row[0]
        else: path += "/dummy.txt"
    else:
        show_path = path

    file_id = find_file(db, path=path)

    filters = review_filters.Filters()
    filters.load(db, repository=repository, recursive=True)

    reviewers = []
    watchers = []

    for user_id, (filter_type, delegate) in filters.listUsers(db, file_id).items():
        if filter_type == 'reviewer': reviewers.append(user_id)
        else: watchers.append(user_id)

    result = "Path: %s\n" % show_path

    reviewers_found = False
    watchers_found = False

    for reviewer_id in sorted(reviewers):
        if not reviewers_found:
            result += "\nReviewers:\n"
            reviewers_found = True

        reviewer = dbutils.User.fromId(db, reviewer_id)
        result += "  %s <%s>\n" % (reviewer.fullname, reviewer.email)

    for watcher_id in sorted(watchers):
        if not watchers_found:
            result += "\nWatchers:\n"
            watchers_found = True

        watcher = dbutils.User.fromId(db, watcher_id)
        result += "  %s <%s>\n" % (watcher.fullname, watcher.email)

    if not reviewers_found and not watchers_found:
        result += "\nNo matching filters found.\n"

    return result

def rebasebranch(req, db, user):
    repository = gitutils.Repository.fromParameter(db, req.getParameter("repository", user.getPreference(db, "defaultRepository")))

    branch_name = req.getParameter("name")
    base_name = req.getParameter("base")

    branch = dbutils.Branch.fromName(db, repository, branch_name)
    base = dbutils.Branch.fromName(db, repository, base_name)

    branch.rebase(db, base)

    db.commit()

    return "ok"

def checkserial(req, db, user):
    review_id = req.getParameter("review", filter=int)
    check_serial = req.getParameter("serial", filter=int)

    cursor = db.cursor()
    cursor.execute("SELECT serial FROM reviews WHERE id=%s", (review_id,))

    (current_serial,) = cursor.fetchone()

    req.content_type = "text/plain"

    if check_serial == current_serial: return "current:%d" % user.getPreference(db, "review.updateCheckInterval")
    elif check_serial < current_serial: return "old"
    else: return "invalid"

def findreview(req, db, user):
    sha1 = req.getParameter("sha1")

    try:
        repository = gitutils.Repository.fromSHA1(db, sha1)
        commit = gitutils.Commit.fromSHA1(db, repository, repository.revparse(sha1))
    except:
        raise page.utils.DisplayMessage, "No such commit: '%s'" % sha1

    cursor = db.cursor()
    cursor.execute("""SELECT reviews.id
                        FROM reviews
                        JOIN branches ON (branches.id=reviews.branch)
                        JOIN reachable ON (reachable.branch=branches.id)
                       WHERE reachable.commit=%s""",
                   (commit.getId(db),))

    try:
        review_id = cursor.fetchone()[0]
    except:
        cursor.execute("""SELECT reviewchangesets.review
                            FROM reviewchangesets
                            JOIN changesets ON (changesets.id=reviewchangesets.changeset)
                           WHERE changesets.child=%s""",
                       (commit.getId(db),))

        try:
            review_id = cursor.fetchone()[0]
        except:
            raise page.utils.DisplayMessage, "No review found!"

    raise page.utils.MovedTemporarily, "/r/%d?highlight=%s#%s" % (review_id, sha1, sha1)

def suggestreview(req, db, user):
    repository_id = req.getParameter("repository", filter=int)
    sha1 = req.getParameter("sha1")

    repository = gitutils.Repository.fromId(db, repository_id)
    commit = gitutils.Commit.fromSHA1(db, repository, sha1)

    cursor = db.cursor()
    suggestions = {}

    def addSuggestions():
        for review_id, summary in cursor:
            review = dbutils.Review.fromId(db, review_id, load_commits=False)
            if review.state != 'dropped':
                suggestions[str(review_id)] = "(%s) %s" % (review.getReviewState(db), summary)

    summary = commit.summary()
    while True:
        match = re.search("[A-Z][A-Z0-9]*-[0-9]+", summary)
        if match:
            pattern = "r/%" + match.group(0) + "%"
            cursor.execute("""SELECT reviews.id, reviews.summary
                                FROM reviews
                                JOIN branches ON (reviews.branch=branches.id)
                               WHERE branches.name LIKE %s""",
                           (pattern,))
            addSuggestions()

            summary = summary[match.end():]
        else:
            break

    cursor.execute("""SELECT reviews.id, reviews.summary
                        FROM reviews
                       WHERE reviews.summary=%s""",
                   (commit.summary(),))
    addSuggestions()

    return json_encode(suggestions)

def rawstatistics(req, db, user):
    cursor = db.cursor()
    result = ""

    result += "Statistics:\n\n"

    def line(key, value, width=40):
        key = key.decode("utf-8")
        if len(key) > width:
            key = u"..." + key[len(key) - 37:]
        return "%s%s: %s\n" % (" " * (width - len(key)), key.encode("utf-8"), value)

    def lines(row):
        return "% 10s / % 10s" % ("-%d" % row[0], "+%d" % row[1])

    skip_files = []
    for path in ["modules/dom/selftest/opatom.ot",
                 "modules/style/src/css_grammar.cpp",
                 "platforms/core/encodingbin.cpp",
                 "modules/logdoc/src/html5/html5entity_nodes_init.inl",
                 "modules/logdoc/src/html5/html5entity_nodes_init2.inl"]:
        skip_files.append(find_file(db, path=path))
    skip_files = ", ".join(map(str, skip_files))

    cursor.execute("""SELECT fileDeleted, fileAdded, SUM(deleteCount), SUM(insertCount)
                        FROM (SELECT fileversions.new_sha1='0000000000000000000000000000000000000000' AS fileDeleted,
                                     fileversions.old_sha1='0000000000000000000000000000000000000000' AS fileAdded,
                                     chunks.deleteCount AS deleteCount,
                                     chunks.insertCount AS insertCount
                                FROM chunks
                                JOIN changesets ON (chunks.changeset=changesets.id)
                                JOIN fileversions ON (chunks.file=fileversions.file
                                                  AND changesets.id=fileversions.changeset)
                               WHERE chunks.file NOT IN (%s)) AS temporary
                    GROUP BY fileDeleted, fileAdded""" % skip_files)
    rows = cursor.fetchall()

    deleted_files = None
    added_files = None
    modified_files = None

    assert len(rows) == 3

    for row in rows:
        if row[0]: deleted_files = row
        elif row[1]: added_files = row
        else: modified_files = row

    result += line("Indexed changes (added/deleted files)", lines((deleted_files[2], added_files[3])))
    result += line("Indexed changes (modified files)", lines((modified_files[2], modified_files[3])))

    cursor.execute("""SELECT fileDeleted, fileAdded, SUM(deleted), SUM(inserted)
                        FROM (SELECT fileversions.new_sha1='0000000000000000000000000000000000000000' AS fileDeleted,
                                     fileversions.old_sha1='0000000000000000000000000000000000000000' AS fileAdded,
                                     reviewfiles.deleted AS deleted,
                                     reviewfiles.inserted AS inserted
                                FROM reviewfiles
                                JOIN fileversions USING (changeset, file)
                               WHERE reviewfiles.state='reviewed'
                                 AND reviewfiles.file NOT IN (%s)) AS temporary
                    GROUP BY fileDeleted, fileAdded""" % skip_files)
    rows = cursor.fetchall()

    deleted_files = None
    added_files = None
    modified_files = None

    for row in rows:
        if row[0] is None and row[1] is None: continue
        if row[0]: deleted_files = row
        elif row[1]: added_files = row
        else:
            assert row[0] is False and row[1] is False
            modified_files = row

    result += line("Reviewed changes (added/deleted files)", lines((deleted_files[2], added_files[3])))
    result += line("Reviewed changes (modified files)", lines((modified_files[2], modified_files[3])))

    cursor.execute("""SELECT uid, fileDeleted, fileAdded, SUM(deleted), SUM(inserted)
                        FROM (SELECT reviewfiles.reviewer AS uid,
                                     fileversions.new_sha1='0000000000000000000000000000000000000000' AS fileDeleted,
                                     fileversions.old_sha1='0000000000000000000000000000000000000000' AS fileAdded,
                                     reviewfiles.deleted AS deleted,
                                     reviewfiles.inserted AS inserted
                                FROM reviewfiles
                                JOIN fileversions USING (changeset, file)
                               WHERE reviewfiles.state='reviewed'
                                 AND reviewfiles.file NOT IN (%s)) AS temporary
                    GROUP BY uid, fileDeleted, fileAdded""" % skip_files)
    rows = cursor.fetchall()

    result += "\nReviewers (added/deleted files):\n\n"

    users = {}
    for row in rows:
        if row[1] or row[2]:
            data = users.setdefault(row[0], [0, dbutils.User.fromId(db, row[0]).fullname, [0, 0]])
            data[0] += row[3] + row[4]
            data[2][0] += row[3]
            data[2][1] += row[4]
    for total, fullname, counts in sorted(users.values(), reverse=True)[:10]:
        result += line(fullname, lines(counts))

    result += "\nReviewers (modified files):\n\n"

    users = []
    for row in rows:
        if not row[1] and not row[2]:
            users.append((row[3] + row[4], dbutils.User.fromId(db, row[0]).fullname, (row[3], row[4])))
    for total, fullname, counts in sorted(users, reverse=True)[:10]:
        result += line(fullname, lines(counts) + (" [%4d]" % (int(float(total)) / 365)))

    cursor.execute("""SELECT file, COUNT(*)
                        FROM commentchains
                       WHERE file IS NOT NULL
                    GROUP BY file""")

    result += "\nMost commented files:\n\n"

    files = []

    for file_id, count in cursor:
        files.append((count, file_id))

    for count, file_id in sorted(files, reverse=True)[:10]:
        result += line(describe_file(db, file_id), count, width=60)

    result += "\nIgnored files:\n\n"

    for file_id in [int(s.strip()) for s in skip_files.split(",")]:
        result += "  %s\n" % describe_file(db, file_id)

    result += "\nover, out\n"

    return result

def loadmanifest(req, db, user):
    author = req.getParameter("author")
    name = req.getParameter("name")

    try:
        manifest = extensions.loadManifest(extensions.getExtensionPath(author, name))
        return "That's a valid manifest, friend."
    except Exception, e:
        return str(e)

def processcommits(req, db, user):
    review_id = req.getParameter("review", filter=int)
    commit_ids = map(int, req.getParameter("commits").split(","))

    review = dbutils.Review.fromId(db, review_id)
    all_commits = [gitutils.Commit.fromId(db, review.repository, commit_id) for commit_id in commit_ids]
    commitset = log_commitset.CommitSet(all_commits)

    heads = commitset.getHeads()
    tails = commitset.getTails()

    if len(heads) != 1:
        return "invalid commit-set; multiple heads"
    if len(tails) != 1:
        return "invalid commit-set; multiple tails"

    old_head = gitutils.Commit.fromSHA1(db, review.repository, tails.pop())
    new_head = heads.pop()

    output = cStringIO.StringIO()

    extensions.executeProcessCommits(db, user, review, all_commits, old_head, new_head, output)

    return output.getvalue()

operations = { "fetchlines": operation.fetchlines.FetchLines(),
               "reviewersandwatchers": operation.createreview.ReviewersAndWatchers(),
               "submitreview": operation.createreview.SubmitReview(),
               "fetchremotebranches": operation.createreview.FetchRemoteBranches(),
               "fetchremotebranch": operation.createreview.FetchRemoteBranch(),
               "validatecommentchain": operation.createcomment.ValidateCommentChain(),
               "createcommentchain": operation.createcomment.CreateCommentChain(),
               "createcomment": operation.createcomment.CreateComment(),
               "reopenresolvedcommentchain": operation.manipulatecomment.ReopenResolvedCommentChain(),
               "reopenaddressedcommentchain": operation.manipulatecomment.ReopenAddressedCommentChain(),
               "resolvecommentchain": operation.manipulatecomment.ResolveCommentChain(),
               "morphcommentchain": operation.manipulatecomment.MorphCommentChain(),
               "updatecomment": operation.manipulatecomment.UpdateComment(),
               "deletecomment": operation.manipulatecomment.DeleteComment(),
               "markchainsasread": operation.manipulatecomment.MarkChainsAsRead(),
               "closereview": operation.manipulatereview.CloseReview(),
               "dropreview": operation.manipulatereview.DropReview(),
               "reopenreview": operation.manipulatereview.ReopenReview(),
               "pingreview": operation.manipulatereview.PingReview(),
               "updatereview": operation.manipulatereview.UpdateReview(),
               "setfullname": operation.manipulateuser.SetFullname(),
               "setemail": operation.manipulateuser.SetEmail(),
               "setgitemails": operation.manipulateuser.SetGitEmails(),
               "changepassword": operation.manipulateuser.ChangePassword(),
               "getassignedchanges": operation.manipulateassignments.GetAssignedChanges(),
               "setassignedchanges": operation.manipulateassignments.SetAssignedChanges(),
               "watchreview": watchreview,
               "unwatchreview": unwatchreview,
               "addreviewfilters": operation.manipulatefilters.AddReviewFilters(),
               "removereviewfilter": operation.manipulatefilters.RemoveReviewFilter(),
               "queryparentfilters": queryparentfilters,
               "applyparentfilters": applyparentfilters,
               "suggestupstreams": operation.rebasereview.SuggestUpstreams(),
               "checkrebase": operation.rebasereview.CheckRebase(),
               "preparerebase": operation.rebasereview.PrepareRebase(),
               "cancelrebase": operation.rebasereview.CancelRebase(),
               "rebasereview": operation.rebasereview.RebaseReview(),
               "revertrebase": operation.rebasereview.RevertRebase(),
               "addfilter": addfilter,
               "deletefilter": deletefilter,
               "reapplyfilters": reapplyfilters,
               "markfiles": operation.markfiles.MarkFiles(),
               "submitchanges": operation.draftchanges.SubmitChanges(),
               "abortchanges": operation.draftchanges.AbortChanges(),
               "reviewstatechange": operation.draftchanges.ReviewStateChange(),
               "savesettings": savesettings,
               "showfilters": showfilters,
               "rebasebranch": rebasebranch,
               "checkserial": checkserial,
               "suggestreview": suggestreview,
               "rawstatistics": rawstatistics,
               "blame": operation.blame.Blame(),
               "checkbranchtext": page.checkbranch.renderCheckBranch,
               "addcheckbranchnote": page.checkbranch.addNote,
               "deletecheckbranchnote": page.checkbranch.deleteNote,
               "addrepository": operation.addrepository.AddRepository(),
               "storeresource": operation.editresource.StoreResource(),
               "resetresource": operation.editresource.ResetResource(),
               "restoreresource": operation.editresource.RestoreResource(),
               "addnewsitem": operation.news.AddNewsItem(),
               "editnewsitem": operation.news.EditNewsItem(),
               "getautocompletedata": operation.autocompletedata.GetAutoCompleteData(),
               "addrecipientfilter": operation.recipientfilter.AddRecipientFilter(),
               "trackedbranchlog": operation.trackedbranch.TrackedBranchLog(),
               "disabletrackedbranch": operation.trackedbranch.DisableTrackedBranch(),
               "triggertrackedbranchupdate": operation.trackedbranch.TriggerTrackedBranchUpdate(),
               "enabletrackedbranch": operation.trackedbranch.EnableTrackedBranch(),
               "deletetrackedbranch": operation.trackedbranch.DeleteTrackedBranch(),
               "addtrackedbranch": operation.trackedbranch.AddTrackedBranch(),
               "restartservice": operation.servicemanager.RestartService(),
               "getservicelog": operation.servicemanager.GetServiceLog() }

pages = { "showreview": page.showreview.renderShowReview,
          "showcommit": page.showcommit.renderShowCommit,
          "dashboard": page.dashboard.renderDashboard,
          "showcomment": page.showcomment.renderShowComment,
          "showcomments": page.showcomment.renderShowComments,
          "showfile": page.showfile.renderShowFile,
          "statistics": page.statistics.renderStatistics,
          "home": page.home.renderHome,
          "config": page.config.renderConfig,
          "branches": page.branches.renderBranches,
          "tutorial": page.tutorial.renderTutorial,
          "news": page.news.renderNews,
          "managereviewers": page.managereviewers.renderManageReviewers,
          "log": page.showbranch.renderShowBranch,
          "checkbranch": page.checkbranch.renderCheckBranch,
          "filterchanges": page.filterchanges.renderFilterChanges,
          "showtree": page.showtree.renderShowTree,
          "findreview": findreview,
          "showbatch": page.showbatch.renderShowBatch,
          "showreviewlog": page.showreviewlog.renderShowReviewLog,
          "createreview": page.createreview.renderCreateReview,
          "newrepository": page.addrepository.renderNewRepository,
          "confirmmerge": page.confirmmerge.renderConfirmMerge,
          "editresource": page.editresource.renderEditResource,
          "search": page.search.renderSearch,
          "repositories": page.repositories.renderRepositories,
          "services": page.services.renderServices }

if configuration.extensions.ENABLED:
    import extensions
    import operation.extensioninstallation
    import page.manageextensions

    operations["installextension"] = operation.extensioninstallation.InstallExtension()
    operations["uninstallextension"] = operation.extensioninstallation.UninstallExtension()
    operations["reinstallextension"] = operation.extensioninstallation.ReinstallExtension()
    operations["loadmanifest"] = loadmanifest
    operations["processcommits"] = processcommits
    pages["manageextensions"] = page.manageextensions.renderManageExtensions

if configuration.base.AUTHENTICATION_MODE == "critic" and configuration.base.SESSION_TYPE == "cookie":
    import operation.usersession
    import page.login

    operations["validatelogin"] = operation.usersession.ValidateLogin()
    operations["endsession"] = operation.usersession.EndSession()
    pages["login"] = page.login.renderLogin

def main(environ, start_response):
    request_start = time.time()

    db = dbutils.Database()
    user = None

    try:
        try:
            req = request.Request(db, environ, start_response)

            if req.user is None:
                if configuration.base.AUTHENTICATION_MODE == "critic":
                    if configuration.base.SESSION_TYPE == "httpauth":
                        req.setStatus(401)
                        req.addResponseHeader("WWW-Authenticate", "Basic realm=\"Critic\"")
                        req.start()
                        return
                    elif configuration.base.ALLOW_ANONYMOUS_USER or req.path in ("login", "validatelogin"):
                        user = dbutils.User.makeAnonymous()
                    elif req.method == "GET":
                        raise page.utils.NeedLogin, req
                    else:
                        # Don't try to redirect POST requests to the login page.
                        req.setStatus(403)
                        req.start()
                        return
            else:
                try:
                    user = dbutils.User.fromName(db, req.user)
                except dbutils.NoSuchUser:
                    cursor = db.cursor()
                    cursor.execute("""INSERT INTO users (name, email, fullname)
                                           VALUES (%s, %s, %s)
                                        RETURNING id""",
                                   (req.user, getUserEmailAddress(req.user), req.user))
                    user = dbutils.User.fromId(db, cursor.fetchone()[0])
                    db.commit()

            user.loadPreferences(db)

            if user.status == 'retired':
                cursor = db.cursor()
                cursor.execute("UPDATE users SET status='current' WHERE id=%s", (user.id,))
                user = dbutils.User.fromId(db, user.id)
                db.commit()

            if not user.getPreference(db, "debug.profiling.databaseQueries"):
                db.disableProfiling()

            if not req.path:
                if user.isAnonymous():
                    location = "tutorial"
                else:
                    location = user.getPreference(db, "defaultPage")

                if req.query:
                    location += "?" + req.query

                req.setStatus(307)
                req.addResponseHeader("Location", location)
                req.start()
                return

            if req.path == "redirect":
                target = req.getParameter("target", "/")

                if req.method == "POST":
                    # Don't use HTTP redirect for POST requests.

                    req.setContentType("text/html")
                    req.start()

                    yield "<meta http-equiv='refresh' content='0; %s'>" % htmlify(target)
                    return
                else:
                    raise page.utils.MovedTemporarily, target

            if req.path.startswith("!/"):
                req.path = req.path[2:]
            elif configuration.extensions.ENABLED:
                handled = extensions.executePage(db, req, user)
                if handled:
                    req.start()
                    yield handled
                    return

            if req.path.startswith("r/"):
                req.query = "id=" + req.path[2:] + ("&" + req.query if req.query else "")
                req.path = "showreview"

            if configuration.extensions.ENABLED:
                match = RE_EXTENSION_RESOURCE.match(req.path)
                if match:
                    content_type, resource = extensions.getExtensionResource(req, db, user, match.group(1))
                    if resource:
                        req.setContentType(content_type)
                        req.start()
                        yield resource
                        return
                    else:
                        req.setStatus(404)
                        req.start()
                        return

            if req.path.startswith("download/"): operation = download
            else: operation = operations.get(req.path)
            if operation:
                req.setContentType("text/plain")

                try: result = operation(req, db, user)
                except OperationError, error: result = error
                except page.utils.DisplayMessage, message:
                    result = "error:" + message.title
                    if message.body: result += "  " + message.body
                except Exception, exception: result = "error:\n" + "".join(traceback.format_exception(*sys.exc_info()))

                if isinstance(result, (OperationResult, OperationError)):
                    req.setContentType("text/json")

                    if isinstance(result, OperationResult):
                        if db.profiling: result.set("__profiling__", formatDBProfiling(db))
                        result.addResponseHeaders(req)
                else:
                    req.setContentType("text/plain")

                req.start()

                if isinstance(result, unicode): yield result.encode("utf8")
                else: yield str(result)

                return

            override_user = req.getParameter("user", None)

            while True:
                pagefn = pages.get(req.path)
                if pagefn:
                    try:
                        if not user.isAnonymous() and override_user:
                            user = dbutils.User.fromName(db, override_user)

                        req.setContentType("text/html")

                        result = pagefn(req, db, user)
                    except gitutils.NoSuchRepository, error:
                        raise page.utils.DisplayMessage("Invalid URI Parameter!", error.message)
                    except dbutils.NoSuchUser, error:
                        raise page.utils.DisplayMessage("Invalid URI Parameter!", error.message)

                    if isinstance(result, str) or isinstance(result, Document):
                        req.start()
                        yield str(result)
                    else:
                        for fragment in result:
                            req.start()
                            yield str(fragment)

                    yield "<!-- total request time: %.2f ms -->" % ((time.time() - request_start) * 1000)

                    if db.profiling:
                        yield "<!--\n\n%s\n\n -->" % formatDBProfiling(db)

                    return

                path = req.path

                try:
                    repository = gitutils.Repository.fromName(db, path.split("/", 1)[0])
                    if repository: path = path.split("/", 1)[1]
                except:
                    repository = None

                def revparse(item):
                    try: return gitutils.getTaggedCommit(repository, repository.revparse(item))
                    except: raise

                if repository is None:
                    review_id = req.getParameter("review", None, filter=int)

                    if review_id:
                        cursor = db.cursor()
                        cursor.execute("SELECT repository FROM branches JOIN reviews ON (reviews.branch=branches.id) WHERE reviews.id=%s", (review_id,))
                        try:
                            repository = gitutils.Repository.fromId(db, cursor.fetchone()[0])
                            def revparse(item):
                                if re.match("^[0-9a-f]+$", item):
                                    cursor.execute("SELECT sha1 FROM commits JOIN changesets ON (changesets.child=commits.id) JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id) WHERE reviewchangesets.review=%s AND commits.sha1 LIKE %s", (review_id, item + "%"))
                                    try: return cursor.fetchone()[0]
                                    except: return gitutils.getTaggedCommit(repository, repository.revparse(item))
                        except: pass

                if repository is None:
                    repository = gitutils.Repository.fromName(db, user.getPreference(db, "defaultRepository"))

                    if gitutils.re_sha1.match(path):
                        if repository and not repository.iscommit(path):
                            repository = None

                        if not repository:
                            repository = gitutils.Repository.fromSHA1(db, path)

                if repository:
                    try:
                        items = filter(None, map(revparse, path.split("..")))

                        if len(items) == 1:
                            req.query = "repository=%d&sha1=%s&%s" % (repository.id, items[0], req.query)
                            req.path = "showcommit"
                            continue
                        elif len(items) == 2:
                            req.query = "repository=%d&from=%s&to=%s&%s" % (repository.id, items[0], items[1], req.query)
                            req.path = "showcommit"
                            continue
                    except: pass

                break

            req.setStatus(404)
            raise page.utils.DisplayMessage, ("Not found!", "Page not handled: /%s" % path)
        except GeneratorExit:
            raise
        except page.utils.NotModified:
            req.setStatus(304)
            req.start()
            return
        except page.utils.MovedTemporarily, redirect:
            req.setStatus(307)
            req.addResponseHeader("Location", redirect.location)
            if redirect.no_cache:
                req.addResponseHeader("Cache-Control", "no-cache")
            req.start()
            return
        except request.MissingWSGIRemoteUser, err:
            # req object is not initialized yet.
            start_response("200 OK", [("Content-Type", "text/html")])
            yield """\
<pre>error: Critic was configured with '--auth-mode host' but there was no REMOTE_USER
variable in the WSGI environ dict provided by the web server.

To fix this you can either reinstall Critic using '--auth-mode critic' (to let Critic handle user authentication
automatically), or you can configure user authentication properly in the web server.  For apache2, the latter can be done
by adding the something like the following to the apache site configuration for Critic:

        &lt;Location /&gt;
                AuthType Basic
                AuthName "Authentication Required"
                AuthUserFile "/path/to/critic-main.htpasswd.users"
                Require valid-user
        &lt;/Location&gt;

If you need more dynamic http authentication you can instead setup mod_wsgi with a custom WSGIAuthUserScript
directive.  This will cause the provided credentials to be passed to a Python function called check_password()
that you can implement yourself.  This way you can validate the user/pass via any existing database or for
example an LDAP server.  For more information on setting up such authentication in apache2, see:
<a href="http://code.google.com/p/modwsgi/wiki/AccessControlMechanisms#Apache_Authentication_Provider">
http://code.google.com/p/modwsgi/wiki/AccessControlMechanisms#Apache_Authentication_Provider</a></pre>"""
            return
        except page.utils.DisplayMessage, message:
            document = page.utils.displayMessage(db, req, user, title=message.title, message=message.body, review=message.review, is_html=message.html)

            req.setContentType("text/html")
            req.start()

            yield str(document)
            return
        except:
            error_message = traceback.format_exc()

            environ["wsgi.errors"].write(error_message)

            db.rollback()

            if not user or user.hasRole(db, "developer"):
                title = "You broke the system again:"
                body = error_message
                body_html = "<pre>%s</pre>" % htmlify(body)
            else:
                prefix = dbutils.getURLPrefix(db)

                x_forwarded_host = req.getRequestHeader("X-Forwarded-Host")
                if x_forwarded_host: prefix = "https://" + x_forwarded_host

                url = "%s/%s?%s" % (prefix, req.path, req.query)

                mailutils.sendExceptionMessage("wsgi", ("User:   %s\nMethod: %s\nPath:   %s\nQuery:  %s\nURL:    %s\n\n%s"
                                                        % (req.user, req.method, req.path, req.query, url, error_message)))

                title = "Darn! It seems we have a problem..."
                body = "A message has been sent to the system administrator(s) with details about the problem."
                body_html = body

            if not req.isStarted():
                req.setStatus(500)
                req.setContentType("text/plain")
                req.start()
                yield "%s\n%s\n\n%s" % (title, "=" * len(title), body)
            elif req.getContentType().startswith("text/html"):
                # Close a bunch of tables, in case we're in any.  Not pretty,
                # but probably makes the end result prettier.
                yield "</table></table></table></table></div><div class='fatal'><table align=center><tr><td><h1>%s</h1><p>%s</p>" % (title, body_html)
    finally:
        db.rollback()
        db.close()
