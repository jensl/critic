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
import gitutils
import time
import re
import itertools
import traceback
import cStringIO
import wsgiref.util

from htmlutils import htmlify, Document
from profiling import formatDBProfiling
from textutils import json_encode, reflow

import request
import dbutils
import reviewing.filters as review_filters
import log.commitset as log_commitset
import diff
import mailutils
import configuration
import auth
import htmlutils
import api
import jsonapi

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
import operation.checkrebase
import operation.applyfilters
import operation.savesettings
import operation.searchreview
import operation.registeruser
import operation.brancharchiving

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
import page.rebasetrackingreview
import page.createuser
import page.verifyemail
import page.manageextensions

try:
    from customization.email import getUserEmailAddress
except ImportError:
    def getUserEmailAddress(_username):
        return None

if configuration.extensions.ENABLED:
    RE_EXTENSION_RESOURCE = re.compile("^extension-resource/([a-z0-9][-._a-z0-9]+(?:/[a-z0-9][-._a-z0-9]+)+)$", re.IGNORECASE)

from operation import OperationResult, OperationError, OperationFailureMustLogin

def setContentTypeFromPath(req):
    match = re.search("\\.([a-z]+)$", req.path)
    if match:
        req.setContentType(configuration.mimetypes.MIMETYPES.get(match.group(1), "text/plain"))
    else:
        req.setContentType("text/plain")

def handleStaticResource(req):
    if req.path == "static-resource/":
        req.setStatus(403)
        req.setContentType("text/plain")
        req.start()
        return ["Directory listing disabled!"]
    resource_path = os.path.join(configuration.paths.INSTALL_DIR,
                                 "resources",
                                 req.path.split("/", 1)[1])
    if os.path.abspath(resource_path) != resource_path:
        raise OperationError("invalid path")
    if not os.path.isfile(resource_path):
        req.setStatus(404)
        req.setContentType("text/plain")
        req.start()
        return ["No such resource!"]
    last_modified = htmlutils.mtime(resource_path)
    if req.query and req.query == htmlutils.base36(last_modified):
        HTTP_DATE = "%a, %d %b %Y %H:%M:%S GMT"
        req.addResponseHeader("Last-Modified", time.strftime(HTTP_DATE, time.gmtime(last_modified)))
        req.addResponseHeader("Expires", time.strftime(HTTP_DATE, time.gmtime(time.time() + 2592000)))
        req.addResponseHeader("Cache-Control", "max-age=2592000")
    setContentTypeFromPath(req)
    req.start()
    with open(resource_path, "r") as resource_file:
        return [resource_file.read()]

def download(req, db, user):
    sha1 = req.getParameter("sha1")

    try:
        repository_arg = req.getParameter("repository", default=None)
        if repository_arg:
            repository = gitutils.Repository.fromParameter(db, repository_arg)
        else:
            repository = user.getDefaultRepository(db)
    except gitutils.NoSuchRepository as error:
        raise page.utils.DisplayMessage(
            title="No such repository",
            body=error.message,
            status=404)

    try:
        git_object = repository.fetch(sha1)
    except gitutils.GitReferenceError as error:
        raise page.utils.DisplayMessage(
            title="File not found",
            body=error.message,
            status=404)

    if git_object.type != "blob":
        raise page.utils.DisplayMessage(
            title="File not found",
            body=("%s is a %s, not a blob"
                  % (git_object.sha1[:8], git_object.type)),
            status=404)

    setContentTypeFromPath(req)

    return git_object.data

def watchreview(req, db, user):
    review_id = req.getParameter("review", filter=int)
    user_name = req.getParameter("user")

    cursor = db.cursor()

    user = dbutils.User.fromName(db, user_name)

    cursor.execute("SELECT 1 FROM reviewusers WHERE review=%s AND uid=%s", (review_id, user.id))

    if not cursor.fetchone():
        cursor.execute("INSERT INTO reviewusers (review, uid, type) VALUES (%s, %s, 'manual')", (review_id, user.id))

        cursor.execute("""SELECT uid, include
                            FROM reviewrecipientfilters
                           WHERE review=%s
                             AND (uid=%s OR uid IS NULL)""",
                       (review_id, user.id))

        default_include = True
        user_include = None

        for user_id, include in cursor:
            if user_id is None:
                default_include = include
            else:
                user_include = include

        if not default_include and user_include is None:
            cursor.execute("""INSERT INTO reviewrecipientfilters (review, uid, include)
                                   VALUES (%s, %s, true)""",
                           (review_id, user.id))

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

def setfullname(req, db, user):
    fullname = req.getParameter("fullname")

    cursor = db.cursor()
    cursor.execute("UPDATE users SET fullname=%s WHERE id=%s", (fullname, user.id))

    db.commit()

    return "ok"

def showfilters(req, db, user):
    path = req.getParameter("path", "/")
    repo_name = req.getParameter("repository", None)
    if not repo_name:
        user = req.getParameter("user", req.user)
        if not user:
            raise page.utils.DisplayMessage("The URL must contain either a repository or a user parameter or both.")
        repo_name = dbutils.User.fromName(db, user).getPreference(db, "defaultRepository")
    repository = gitutils.Repository.fromParameter(db, repo_name)

    path = path.rstrip("/")

    if repository.getHead(db).isDirectory(path):
        show_path = path + "/"
        path += "/dummy.txt"
    else:
        show_path = path

    file_id = dbutils.find_file(db, path=path)

    filters = review_filters.Filters()
    filters.setFiles(db, [file_id])
    filters.load(db, repository=repository, recursive=True)

    reviewers = []
    watchers = []

    for user_id, (filter_type, _delegate) in filters.listUsers(file_id).items():
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

def findreview(req, db, _user):
    sha1 = req.getParameter("sha1")

    try:
        repository = gitutils.Repository.fromSHA1(db, sha1)
        commit = gitutils.Commit.fromSHA1(db, repository, repository.revparse(sha1))
    except gitutils.GitReferenceError as error:
        raise page.utils.DisplayMessage(error.message)

    cursor = db.cursor()
    cursor.execute("""SELECT reviews.id
                        FROM reviews
                        JOIN branches ON (branches.id=reviews.branch)
                        JOIN reachable ON (reachable.branch=branches.id)
                       WHERE reachable.commit=%s""",
                   (commit.getId(db),))

    row = cursor.fetchone()

    if row:
        review_id = row[0]
    else:
        cursor.execute("""SELECT reviewchangesets.review
                            FROM reviewchangesets
                            JOIN changesets ON (changesets.id=reviewchangesets.changeset)
                           WHERE changesets.child=%s""",
                       (commit.getId(db),))

        row = cursor.fetchone()

        if row:
            review_id = row[0]
        else:
            raise page.utils.DisplayMessage("No review found!")

    raise page.utils.MovedTemporarily("/r/%d?highlight=%s#%s" % (review_id, sha1, sha1))

def suggestreview(req, db, _user):
    repository_id = req.getParameter("repository", filter=int)
    sha1 = req.getParameter("sha1")

    repository = gitutils.Repository.fromId(db, repository_id)
    commit = gitutils.Commit.fromSHA1(db, repository, sha1)

    cursor = db.cursor()
    suggestions = {}

    def addSuggestions():
        for review_id, summary in cursor:
            review = dbutils.Review.fromId(db, review_id)
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

def loadmanifest(req, _db, _user):
    key = req.getParameter("key")

    if "/" in key:
        author_name, extension_name = key.split("/", 1)
    else:
        author_name, extension_name = None, key

    try:
        extension = extensions.extension.Extension(author_name, extension_name)
    except extensions.extension.ExtensionError as error:
        return str(error)

    try:
        extension.getManifest()
        return "That's a valid manifest, friend."
    except extensions.manifest.ManifestError as error:
        return str(error)

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

    extensions.role.processcommits.execute(db, user, review, all_commits, old_head, new_head, output)

    return output.getvalue()

OPERATIONS = { "fetchlines": operation.fetchlines.FetchLines(),
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
               "setgitemails": operation.manipulateuser.SetGitEmails(),
               "changepassword": operation.manipulateuser.ChangePassword(),
               "requestverificationemail": operation.manipulateuser.RequestVerificationEmail(),
               "deleteemailaddress": operation.manipulateuser.DeleteEmailAddress(),
               "selectemailaddress": operation.manipulateuser.SelectEmailAddress(),
               "addemailaddress": operation.manipulateuser.AddEmailAddress(),
               "getassignedchanges": operation.manipulateassignments.GetAssignedChanges(),
               "setassignedchanges": operation.manipulateassignments.SetAssignedChanges(),
               "watchreview": watchreview,
               "unwatchreview": unwatchreview,
               "addreviewfilters": operation.manipulatefilters.AddReviewFilters(),
               "removereviewfilter": operation.manipulatefilters.RemoveReviewFilter(),
               "queryglobalfilters": operation.applyfilters.QueryGlobalFilters(),
               "applyglobalfilters": operation.applyfilters.ApplyGlobalFilters(),
               "queryparentfilters": operation.applyfilters.QueryParentFilters(),
               "applyparentfilters": operation.applyfilters.ApplyParentFilters(),
               "suggestupstreams": operation.rebasereview.SuggestUpstreams(),
               "checkrebase": operation.rebasereview.CheckRebase(),
               "preparerebase": operation.rebasereview.PrepareRebase(),
               "cancelrebase": operation.rebasereview.CancelRebase(),
               "rebasereview": operation.rebasereview.RebaseReview(),
               "revertrebase": operation.rebasereview.RevertRebase(),
               "addfilter": operation.manipulatefilters.AddFilter(),
               "deletefilter": operation.manipulatefilters.DeleteFilter(),
               "reapplyfilters": operation.manipulatefilters.ReapplyFilters(),
               "countmatchedpaths": operation.manipulatefilters.CountMatchedPaths(),
               "getmatchedpaths": operation.manipulatefilters.GetMatchedPaths(),
               "markfiles": operation.markfiles.MarkFiles(),
               "submitchanges": operation.draftchanges.SubmitChanges(),
               "abortchanges": operation.draftchanges.AbortChanges(),
               "reviewstatechange": operation.draftchanges.ReviewStateChange(),
               "savesettings": operation.savesettings.SaveSettings(),
               "showfilters": showfilters,
               "rebasebranch": rebasebranch,
               "checkserial": checkserial,
               "suggestreview": suggestreview,
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
               "getrepositorypaths": operation.autocompletedata.GetRepositoryPaths(),
               "addrecipientfilter": operation.recipientfilter.AddRecipientFilter(),
               "trackedbranchlog": operation.trackedbranch.TrackedBranchLog(),
               "disabletrackedbranch": operation.trackedbranch.DisableTrackedBranch(),
               "triggertrackedbranchupdate": operation.trackedbranch.TriggerTrackedBranchUpdate(),
               "enabletrackedbranch": operation.trackedbranch.EnableTrackedBranch(),
               "deletetrackedbranch": operation.trackedbranch.DeleteTrackedBranch(),
               "addtrackedbranch": operation.trackedbranch.AddTrackedBranch(),
               "restartservice": operation.servicemanager.RestartService(),
               "getservicelog": operation.servicemanager.GetServiceLog(),
               "checkmergestatus": operation.checkrebase.CheckMergeStatus(),
               "checkconflictsstatus": operation.checkrebase.CheckConflictsStatus(),
               "checkhistoryrewritestatus": operation.checkrebase.CheckHistoryRewriteStatus(),
               "searchreview": operation.searchreview.SearchReview(),
               "registeruser": operation.registeruser.RegisterUser(),
               "archivebranch": operation.brancharchiving.ArchiveBranch(),
               "resurrectbranch": operation.brancharchiving.ResurrectBranch(),
               "schedulebrancharchival": operation.brancharchiving.ScheduleBranchArchival() }

PAGES = { "showreview": page.showreview.renderShowReview,
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
          "services": page.services.renderServices,
          "rebasetrackingreview": page.rebasetrackingreview.RebaseTrackingReview(),
          "createuser": page.createuser.CreateUser(),
          "verifyemail": page.verifyemail.renderVerifyEmail,
          "manageextensions": page.manageextensions.renderManageExtensions }

if configuration.extensions.ENABLED:
    import extensions
    import extensions.role.page
    import extensions.role.processcommits
    import operation.extensioninstallation

    OPERATIONS["installextension"] = operation.extensioninstallation.InstallExtension()
    OPERATIONS["uninstallextension"] = operation.extensioninstallation.UninstallExtension()
    OPERATIONS["reinstallextension"] = operation.extensioninstallation.ReinstallExtension()
    OPERATIONS["clearextensionstorage"] = operation.extensioninstallation.ClearExtensionStorage()
    OPERATIONS["addextensionhookfilter"] = operation.extensioninstallation.AddExtensionHookFilter()
    OPERATIONS["deleteextensionhookfilter"] = operation.extensioninstallation.DeleteExtensionHookFilter()
    OPERATIONS["loadmanifest"] = loadmanifest
    OPERATIONS["processcommits"] = processcommits

if configuration.base.AUTHENTICATION_MODE != "host" and configuration.base.SESSION_TYPE == "cookie":
    import operation.usersession
    import page.login

    if configuration.base.AUTHENTICATION_MODE == "critic":
        OPERATIONS["validatelogin"] = operation.usersession.ValidateLogin()

    OPERATIONS["endsession"] = operation.usersession.EndSession()
    PAGES["login"] = page.login.Login()

def handleException(db, req, user, as_html=False):
    error_message = traceback.format_exc()
    environ = req.getEnvironment()

    environ["wsgi.errors"].write(error_message)

    if not user or not db or not user.hasRole(db, "developer"):
        url = wsgiref.util.request_uri(environ)

        x_forwarded_host = req.getRequestHeader("X-Forwarded-Host")
        if x_forwarded_host:
            original_host = x_forwarded_host.split(",")[0].strip()
            def replace_host(match):
                return match.group(1) + original_host
            url = re.sub("^([a-z]+://)[^/]+", replace_host, url)

        if user and not user.isAnonymous():
            user_string = str(user)
        else:
            user_string = "<anonymous>"

        mailutils.sendExceptionMessage(db,
            "wsgi", "\n".join(["User:   %s" % user_string,
                               "Method: %s" % req.method,
                               "URL:    %s" % url,
                               "",
                               error_message]))

        admin_message_sent = True
    else:
        admin_message_sent = False

    if not user or not db or user.hasRole(db, "developer") \
            or configuration.debug.IS_DEVELOPMENT \
            or configuration.debug.IS_TESTING:
        error_title = "Unexpected error!"
        error_message = error_message.strip()
        if as_html:
            error_message = "<p class='pre inset'>%s</p>" % htmlify(error_message)
        error_body = [error_message]
        if admin_message_sent:
            admin_message_sent = ("A message has been sent to the system "
                                  "administrator(s) with details about the "
                                  "problem.")
            if as_html:
                admin_message_sent = "<p>%s</p>" % admin_message_sent
            error_body.append(admin_message_sent)
    else:
        error_title = "Request failed!"
        error_message = ("An unexpected error occurred while handling the "
                         "request.  A message has been sent to the system "
                         "administrator(s) with details about the problem.  "
                         "Please contact them for further information and/or "
                         "assistance.")
        if as_html:
            error_message = "<p>%s</p>" % error_message
        error_body = [error_message]

    return error_title, error_body

class WrappedResult(object):
    def __init__(self, db, req, user, result):
        self.db = db
        self.req = req
        self.user = user
        self.result = iter(result)
        # Fetch the first block "prematurely," so that errors from it are raised
        # early, and handled by the normal error handling code in main().
        self.first = self.result.next()
        self.failed = False

    def __iter__(self):
        return self

    def next(self):
        if self.failed:
            raise StopIteration

        try:
            if self.first:
                value = self.first
                self.first = None
            else:
                value = self.result.next()

            self.db.rollback()
            return value
        except StopIteration:
            self.db.close()
            raise
        except Exception:
            error_title, error_body = handleException(
                self.db, self.req, self.user)

            self.db.close()

            if self.req.getContentType().startswith("text/html"):
                self.failed = True

                error_body = "".join("<p>%s</p>" % htmlify(part)
                                     for part in error_body)

                # Close a bunch of tables, in case we're in any.  Not
                # pretty, but probably makes the end result prettier.
                return ("</table></table></table></table></div>"
                        "<div class='fatal'><table align=center><tr>"
                        "<td><h1>%s</h1>%s</td></tr></table></div>"
                        % (error_title, error_body))
            else:
                raise StopIteration

def handleRepositoryPath(db, req, user, suffix):
    if "http" not in configuration.base.REPOSITORY_URL_TYPES:
        return False

    components = req.path.split("/")

    for index in range(1, len(components) + 1):
        repository_path = "/".join(components[:index])
        additional_path = "/".join(components[index:])

        if suffix is not None:
            if not repository_path.endswith(suffix):
                continue

        try:
            repository = gitutils.Repository.fromPath(db, repository_path)
        except gitutils.NoSuchRepository:
            continue
        else:
            db.close()

            try:
                repository.invokeGitHttpBackend(req, user, additional_path)
            except gitutils.GitHttpBackendNeedsUser:
                req.requestHTTPAuthentication()

            return True

    return False

def handleDisplayMessage(db, req, message):
    user = db.user

    if user is None:
        user = dbutils.User.makeAnonymous()

    document = page.utils.displayMessage(
        db, req, user, title=message.title, message=message.body,
        review=message.review, is_html=message.html)

    req.setContentType("text/html")
    req.setStatus(message.status)
    req.start()

    return [str(document)]

def handleDisplayFormattedText(db, req, formatted_text):
    user = db.user

    if user is None:
        user = dbutils.User.makeAnonymous()

    document = page.utils.displayFormattedText(
        db, req, user, formatted_text.source)

    req.setContentType("text/html")
    req.start()

    return [str(document)]

def handleMissingWSGIRemoteUser(db, req):
    return handleDisplayMessage(
        db, req, request.DisplayMessage(
            title="Configuration error",
            body="""\
<p>
Critic was configured with "<code>--auth-mode host</code>", meaning the host web
server will authenticate users, but there was no <code>REMOTE_USER</code>
variable in the WSGI environment provided by the web server, indicating it is
not actually configured to authenticate users.
</p>

<p>
To fix this you can either reinstall Critic using "<code>--auth-mode
critic</code>" (to let Critic handle user authentication internally using its
own user database), or you can configure user authentication properly in the web
server.  For Apache 2.x, the latter can be done by adding the something like the
following to the apache site configuration for Critic:
</p>

<pre>
  &lt;Location /&gt;
    AuthType Basic
    AuthName "Authentication Required"
    AuthUserFile "/path/to/critic-main.htpasswd.users"
    Require valid-user
  &lt;/Location&gt;
</pre>

<p>
If you need more dynamic http authentication you can instead setup mod_wsgi with
a custom <code>WSGIAuthUserScript</code> directive.  This will cause the
provided credentials to be passed to a Python function called check_password()
that you can implement yourself.  This way you can validate the user/pass via
any existing database or for example an LDAP server.
</p>

<p>
For more information on setting up such authentication in Apache 2.x, see:
<a href="%(url)s">Apache Authentication Provider</a>.
</p>"""
            % { "url": ("http://code.google.com/p/modwsgi/wiki/"
                        "AccessControlMechanisms#Apache_Authentication_Provider") },
            html=True,
            status=500))

def finishOAuth(db, req, provider):
    try:
        provider.finish(db, req)
    except (auth.InvalidRequest, auth.Failure):
        _, error_body = handleException(
            db, req, dbutils.User.makeAnonymous(), as_html=True)
        raise page.utils.DisplayMessage(
            title="Authentication failed",
            body="".join(error_body),
            html=True)

def process_request(environ, start_response):
    request_start = time.time()

    critic = api.critic.startSession(for_user=True)
    db = critic.database
    user = None

    try:
        try:
            req = request.Request(db, environ, start_response)

            # Handle static resources very early.  We don't bother with checking
            # for an authenticated user; static resources aren't sensitive, and
            # are referenced from special-case resources like the login page and
            # error messages that, that we want to display even if something
            # went wrong with the authentication.
            if req.path.startswith("static-resource/"):
                return handleStaticResource(req)

            if req.path.startswith("externalauth/"):
                provider_name = req.path[len("externalauth/"):]
                if provider_name in auth.PROVIDERS:
                    provider = auth.PROVIDERS[provider_name]
                    authorize_url = provider.start(db, req)
                    if authorize_url:
                        raise request.Found(authorize_url)

            if req.path.startswith("oauth/"):
                provider_name = req.path[len("oauth/"):]
                if provider_name in auth.PROVIDERS:
                    provider = auth.PROVIDERS[provider_name]
                    if isinstance(provider, auth.OAuthProvider):
                        finishOAuth(db, req, provider)

            auth.checkSession(db, req)

            user = req.user
            user.loadPreferences(db)

            if not user.isAnonymous():
                critic.setActualUser(api.user.fetch(critic, user_id=user.id))

            if user.status == 'retired':
                # If a retired user accesses the system, change the status back
                # to 'current' again.
                with db.updating_cursor("users") as cursor:
                    cursor.execute("""UPDATE users
                                         SET status='current'
                                       WHERE id=%s""",
                                   (user.id,))
                user.status = 'current'

            if not user.getPreference(db, "debug.profiling.databaseQueries"):
                db.disableProfiling()

            original_path = req.path

            if not req.path:
                if user.isAnonymous():
                    location = "tutorial"
                else:
                    location = user.getPreference(db, "defaultPage")

                if req.query:
                    location += "?" + req.query

                raise request.MovedTemporarily(location)

            if req.path == "redirect":
                target = req.getParameter("target", "/")

                if req.method == "POST":
                    # Don't use HTTP redirect for POST requests.

                    req.setContentType("text/html")
                    req.start()

                    return ["<meta http-equiv='refresh' content='0; %s'>" % htmlify(target)]
                else:
                    raise request.MovedTemporarily(target)

            # Require a .git suffix on HTTP(S) repository URLs unless the user-
            # agent starts with "git/" (as Git's normally does.)
            #
            # Our objectives are:
            #
            # 1) Not to require Git's user-agent to be its default value, since
            #    the user might have to override it to get through firewalls.
            # 2) Never to send regular user requests to 'git http-backend' by
            #    mistake.
            #
            # This is a compromise.

            if req.getRequestHeader("User-Agent", "").startswith("git/"):
                suffix = None
            else:
                suffix = ".git"

            if handleRepositoryPath(db, req, user, suffix):
                db = None
                return []

            # Extension "page" roles.  Prefixing a path with "!/" bypasses all
            # extensions.
            #
            # Also bypass extensions if the user is anonymous unless general
            # anonymous access is allowed.  If it's not and the user is still
            # anonymous, access was allowed because of a path-based exception,
            # which was not intended to allow access to an extension.
            if req.path.startswith("!/"):
                req.path = req.path[2:]
            elif configuration.extensions.ENABLED:
                handled = extensions.role.page.execute(db, req, user)
                if isinstance(handled, basestring):
                    req.start()
                    return [handled]

            if req.path.startswith("r/"):
                req.updateQuery({ "id": [req.path[2:]] })
                req.path = "showreview"

            if configuration.extensions.ENABLED:
                match = RE_EXTENSION_RESOURCE.match(req.path)
                if match:
                    content_type, resource = extensions.resource.get(req, db, user, match.group(1))
                    if resource:
                        req.setContentType(content_type)
                        if content_type.startswith("image/"):
                            req.addResponseHeader("Cache-Control", "max-age=3600")
                        req.start()
                        return [resource]
                    else:
                        req.setStatus(404)
                        req.start()
                        return []

            if req.path == "api" or req.path.startswith("api/"):
                try:
                    result = jsonapi.handle(critic, req)
                except jsonapi.Error as error:
                    req.setStatus(error.http_status)
                    result = { "error": { "title": error.title,
                                          "message": error.message }}
                else:
                    req.setStatus(200)

                accept_header = req.getRequestHeader("Accept")
                if accept_header == "application/vnd.api+json":
                    default_indent = None
                else:
                    default_indent = 2
                indent = req.getParameter("indent", default_indent, filter=int)
                if indent == 0:
                    # json.encode(..., indent=0) still gives line-breaks, just
                    # no indentation.  This is not so useful, so set indent to
                    # None instead, which disables formatting entirely.
                    indent = None

                req.setContentType("application/vnd.api+json")
                req.start()
                return [json_encode(result, indent=indent)]

            if req.path.startswith("download/"):
                operationfn = download
            else:
                operationfn = OPERATIONS.get(req.path)

            if operationfn:
                result = operationfn(req, db, user)

                if isinstance(result, (OperationResult, OperationError)):
                    req.setContentType("text/json")

                    if isinstance(result, OperationResult):
                        if db.profiling:
                            result.set("__profiling__", formatDBProfiling(db))
                            result.set("__time__", time.time() - request_start)
                elif not req.hasContentType():
                    req.setContentType("text/plain")

                req.start()

                if isinstance(result, unicode):
                    return [result.encode("utf8")]
                else:
                    return [str(result)]

            impersonate_user = user

            if not user.isAnonymous():
                user_parameter = req.getParameter("user", None)
                if user_parameter:
                    impersonate_user = dbutils.User.fromName(db, user_parameter)

            while True:
                pagefn = PAGES.get(req.path)
                if pagefn:
                    req.setContentType("text/html")

                    try:
                        result = pagefn(req, db, impersonate_user)

                        if db.profiling and not (isinstance(result, str) or
                                                 isinstance(result, Document)):
                            source = ""
                            for fragment in result:
                                source += fragment
                            result = source

                        if isinstance(result, str) or isinstance(result, Document):
                            req.start()
                            result = str(result)
                            result += ("<!-- total request time: %.2f ms -->"
                                       % ((time.time() - request_start) * 1000))
                            if db.profiling:
                                result += ("<!--\n\n%s\n\n -->"
                                           % formatDBProfiling(db))
                            return [result]
                        else:
                            result = WrappedResult(db, req, user, result)
                            req.start()

                            # Prevent the finally clause below from closing the
                            # connection.  WrappedResult does it instead.
                            db = None

                            return result
                    except gitutils.NoSuchRepository as error:
                        raise page.utils.DisplayMessage(
                            title="Invalid URI Parameter!",
                            body=error.message)
                    except gitutils.GitReferenceError as error:
                        if error.ref:
                            raise page.utils.DisplayMessage(
                                title="Specified ref not found",
                                body=("There is no ref named \"%s\" in %s."
                                      % (error.ref, error.repository)))
                        elif error.sha1:
                            raise page.utils.DisplayMessage(
                                title="SHA-1 not found",
                                body=error.message)
                        else:
                            raise
                    except dbutils.NoSuchUser as error:
                        raise page.utils.DisplayMessage(
                            title="Invalid URI Parameter!",
                            body=error.message)
                    except dbutils.NoSuchReview as error:
                        raise page.utils.DisplayMessage(
                            title="Invalid URI Parameter!",
                            body=error.message)

                if "/" in req.path:
                    repository_name, _, rest = req.path.partition("/")
                    repository = gitutils.Repository.fromName(db, repository_name)
                    if repository:
                        req.path = rest
                else:
                    repository = None

                def revparsePlain(item):
                    try: return gitutils.getTaggedCommit(repository, repository.revparse(item))
                    except: raise
                revparse = revparsePlain

                if repository is None:
                    review_id = req.getParameter("review", None, filter=int)

                    if review_id:
                        cursor = db.cursor()
                        cursor.execute("""SELECT repository
                                            FROM branches
                                            JOIN reviews ON (reviews.branch=branches.id)
                                           WHERE reviews.id=%s""",
                                       (review_id,))
                        row = cursor.fetchone()
                        if row:
                            repository = gitutils.Repository.fromId(db, row[0])
                            def revparseWithReview(item):
                                if re.match("^[0-9a-f]+$", item):
                                    cursor.execute("""SELECT sha1
                                                        FROM commits
                                                        JOIN changesets ON (changesets.child=commits.id)
                                                        JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                                                       WHERE reviewchangesets.review=%s
                                                         AND commits.sha1 LIKE %s""",
                                                   (review_id, item + "%"))
                                    row = cursor.fetchone()
                                    if row: return row[0]
                                    else: return revparsePlain(item)
                            revparse = revparseWithReview

                if repository is None:
                    repository = gitutils.Repository.fromName(
                        db, user.getPreference(db, "defaultRepository"))

                    if gitutils.re_sha1.match(req.path):
                        if repository and not repository.iscommit(req.path):
                            repository = None

                        if not repository:
                            try:
                                repository = gitutils.Repository.fromSHA1(db, req.path)
                            except gitutils.GitReferenceError:
                                repository = None

                if repository:
                    try:
                        items = filter(None, map(revparse, req.path.split("..")))
                        updated_query = {}

                        if len(items) == 1:
                            updated_query["repository"] = [repository.name]
                            updated_query["sha1"] = [items[0]]
                        elif len(items) == 2:
                            updated_query["repository"] = [repository.name]
                            updated_query["from"] = [items[0]]
                            updated_query["to"] = [items[1]]

                        if updated_query:
                            req.updateQuery(updated_query)
                            req.path = "showcommit"
                            continue
                    except gitutils.GitReferenceError:
                        pass

                break

            raise page.utils.DisplayMessage(
                title="Not found!",
                body="Page not handled: /%s" % original_path,
                status=404)
        except GeneratorExit:
            raise
        except request.HTTPResponse as response:
            return response.execute(db, req)
        except request.MissingWSGIRemoteUser as error:
            return handleMissingWSGIRemoteUser(db, req)
        except page.utils.DisplayMessage as message:
            return handleDisplayMessage(db, req, message)
        except page.utils.DisplayFormattedText as formatted_text:
            return handleDisplayFormattedText(db, req, formatted_text)
        except Exception:
            # crash might be psycopg2.ProgrammingError so rollback to avoid
            # "InternalError: current transaction is aborted" inside handleException()
            if db and db.closed():
                db = None
            elif db:
                db.rollback()

            error_title, error_body = handleException(db, req, user)
            error_body = reflow("\n\n".join(error_body))
            error_message = "\n".join([error_title,
                                       "=" * len(error_title),
                                       "",
                                       error_body])

            assert not req.isStarted()

            req.setStatus(500)
            req.setContentType("text/plain")
            req.start()

            return [error_message]
    finally:
        if db:
            db.close()

if configuration.debug.COVERAGE_DIR:
    def main(environ, start_response):
        import coverage

        def do_process_request(environ, start_response):
            # Apply list() to force the request to be fully performed by this
            # call.  It might return an iterator whose .next() does all the
            # work, and if we just return that from here, the actual work is not
            # subject to coverage measurement.
            return list(process_request(environ, start_response))

        return coverage.call("wsgi", do_process_request, environ, start_response)
else:
    main = process_request
