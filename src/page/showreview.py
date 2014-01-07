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

import datetime
import calendar
import traceback

import base
import dbutils
import gitutils
import htmlutils
import page.utils
import log.html
import reviewing.utils as review_utils
import reviewing.html as review_html
import reviewing.comment as review_comment
import configuration
import diff
import profiling
import linkify

from textutils import json_encode

try:
    from customization.paths import getModuleFromFile
except:
    def getModuleFromFile(repository, filename):
        try:
            base, rest = filename.split("/", 1)
            return base + "/"
        except:
            return None

class SummaryColumn(log.html.SummaryColumn):
    def __init__(self, review, linkToCommit):
        log.html.SummaryColumn.__init__(self, linkToCommit)
        self.__review = review
        self.__cache = {}

    def fillCache(self, db, review):
        cursor = db.cursor()
        cursor.execute("""SELECT DISTINCT assignee, child
                            FROM fullreviewuserfiles
                            JOIN changesets ON (changesets.id=changeset)
                           WHERE review=%s
                             AND state='pending'""",
                       (review.id,))
        for user_id, commit_id in cursor:
            self.__cache.setdefault(commit_id, set()).add(user_id)

    def render(self, db, commit, target, overrides={}):
        user_ids = self.__cache.get(commit.getId(db))
        if user_ids:
            users = ["%s:%s" % (user.fullname, user.status) for user in dbutils.User.fromIds(db, [user_id for user_id in user_ids])]
            target.setAttribute("critic-reviewers", ",".join(sorted(users)))
        log.html.SummaryColumn.render(self, db, commit, target, overrides=overrides)

class ApprovalColumn:
    APPROVED = 1
    TOTAL = 2

    def __init__(self, user, review, type, cache):
        self.__user = user
        self.__review = review
        self.__type = type
        self.__cache = cache

    @staticmethod
    def fillCache(db, user, review, cache, profiler):
        cursor = db.cursor()

        profiler.check("fillCache")

        cursor.execute("""SELECT child, state, COUNT(*), SUM(deleted), SUM(inserted)
                            FROM changesets
                            JOIN reviewfiles ON (changeset=changesets.id)
                           WHERE review=%s
                        GROUP BY child, state""",
                       (review.id,))

        for commit_id, state, nfiles, deleted, inserted in cursor:
            data = cache.get(commit_id)
            if not data: data = cache[commit_id] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            if state == 'reviewed':
                data[3] += nfiles
                data[4] += deleted
                data[5] += inserted
            data[0] += nfiles
            data[1] += deleted
            data[2] += inserted

        profiler.check("fillCache: total")

        cursor.execute("""SELECT child, COALESCE(reviewfilechanges.to, reviewfiles.state) AS effective_state, COUNT(*), SUM(deleted), SUM(inserted)
                            FROM changesets
                            JOIN reviewfiles ON (changeset=changesets.id)
                            JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                 LEFT OUTER JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id
                                                   AND reviewfilechanges.uid=reviewuserfiles.uid
                                                   AND reviewfilechanges.state='draft')
                           WHERE review=%s
                             AND reviewuserfiles.uid=%s
                        GROUP BY child, effective_state""",
                       (review.id, user.id))

        for commit_id, state, nfiles, deleted, inserted in cursor:
            data = cache.get(commit_id)
            if state == 'reviewed':
                data[9] += nfiles
                data[10] += deleted
                data[11] += inserted
            data[6] += nfiles
            data[7] += deleted
            data[8] += inserted

        profiler.check("fillCache: user")

    def __calculate(self, db, commit):
        return self.__cache.get(commit.id, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    def className(self, db, commit):
        if commit:
            (total_nfiles, total_deleted, total_inserted,
             approved_nfiles, approved_deleted, approved_inserted,
             user_total_nfiles, user_total_deleted, user_total_inserted,
             user_approved_nfiles, user_approved_deleted, user_approved_inserted) = self.__calculate(db, commit)

            if user_approved_nfiles == user_total_nfiles:
                category = ""
            else:
                category = " user"
        else:
            category = ""

        if self.__type == ApprovalColumn.APPROVED:
            return "approval" + category
        else:
            return "total" + category

    def heading(self, target):
        if self.__type == ApprovalColumn.APPROVED:
            target.text("Pending")
        else:
            target.text("Total")

    def render(self, db, commit, target, overrides={}):
        (total_nfiles, total_deleted, total_inserted,
         approved_nfiles, approved_deleted, approved_inserted,
         user_total_nfiles, user_total_deleted, user_total_inserted,
         user_approved_nfiles, user_approved_deleted, user_approved_inserted) = self.__calculate(db, commit)

        if self.__type == ApprovalColumn.APPROVED:
            if user_approved_nfiles == user_total_nfiles:
                if approved_nfiles == total_nfiles:
                    target.text()
                elif approved_deleted == total_deleted and approved_inserted == total_inserted:
                    target.span().text("?? %")
                else:
                    target.span().text("%d %%" % int(100.0 * ((total_deleted + total_inserted) - (approved_deleted + approved_inserted)) / (total_deleted + total_inserted)))
            elif user_approved_deleted == user_total_deleted and user_approved_inserted == user_total_inserted:
                target.span().text("?? %")
            else:
                target.span().text("%d %%" % int(100.0 * ((user_total_deleted + user_total_inserted) - (user_approved_deleted + user_approved_inserted)) / (user_total_deleted + user_total_inserted)))
        else:
            if user_approved_deleted == user_total_deleted and user_approved_inserted == user_total_inserted:
                target.span().text("-%d/+%d" % (total_deleted, total_inserted))
            else:
                target.span().text("-%d/+%d" % (user_total_deleted, user_total_inserted))

def notModified(req, db, user, review):
    value = req.getRequestHeader("If-None-Match")
    return review.getETag(db, user) == value

def renderShowReview(req, db, user):
    profiler = profiling.Profiler()

    cursor = db.cursor()

    if user.getPreference(db, "commit.diff.compactMode"): default_compact = "yes"
    else: default_compact = "no"

    compact = req.getParameter("compact", default_compact) == "yes"
    highlight = req.getParameter("highlight", None)

    review_id = req.getParameter("id", filter=int)
    review = dbutils.Review.fromId(db, review_id, load_commits=False, profiler=profiler)

    profiler.check("create review")

    if not review:
        raise page.utils.DisplayMessage("Invalid Review ID", "%d is not a valid review ID." % review_id)

    if review.getETag(db, user) == req.getRequestHeader("If-None-Match"):
        raise page.utils.NotModified

    profiler.check("ETag")

    repository = review.repository

    prefetch_commits = {}

    cursor.execute("""SELECT DISTINCT sha1, child
                        FROM changesets
                        JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                        JOIN commits ON (commits.id=changesets.child)
                       WHERE review=%s""",
                   (review.id,))

    prefetch_commits.update(dict(cursor))

    profiler.check("commits (query)")

    cursor.execute("""SELECT old_head, commits1.sha1, new_head, commits2.sha1, new_upstream, commits3.sha1
                        FROM reviewrebases
             LEFT OUTER JOIN commits AS commits1 ON (commits1.id=old_head)
             LEFT OUTER JOIN commits AS commits2 ON (commits2.id=new_head)
             LEFT OUTER JOIN commits AS commits3 ON (commits3.id=new_upstream)
                       WHERE review=%s""",
                   (review.id,))

    rebases = cursor.fetchall()

    if rebases:
        has_finished_rebases = False

        for old_head_id, old_head_sha1, new_head_id, new_head_sha1, new_upstream_id, new_upstream_sha1 in rebases:
            if old_head_id:
                prefetch_commits[old_head_sha1] = old_head_id
            if new_head_id:
                prefetch_commits[new_head_sha1] = new_head_id
                has_finished_rebases = True
            if new_upstream_id:
                prefetch_commits[new_upstream_sha1] = new_upstream_id

        profiler.check("auxiliary commits (query)")

        if has_finished_rebases:
            cursor.execute("""SELECT commits.sha1, commits.id
                                FROM commits
                                JOIN reachable ON (reachable.commit=commits.id)
                               WHERE branch=%s""",
                           (review.branch.id,))

            prefetch_commits.update(dict(cursor))

            profiler.check("actual commits (query)")

    prefetch_commits = gitutils.FetchCommits(repository, prefetch_commits)

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body(onunload="void(0);")

    def flush(target=None):
        return document.render(stop=target, pretty=not compact)

    def renderHeaderItems(target):
        has_draft_items = review_utils.renderDraftItems(db, user, review, target)

        target = target.div("buttons")

        if not has_draft_items:
            if review.state == "open":
                if review.accepted(db):
                    target.button(id="closeReview", onclick="closeReview();").text("Close Review")
                else:
                    if user in review.owners or user.getPreference(db, "review.pingAnyReview"):
                        target.button(id="pingReview", onclick="pingReview();").text("Ping Review")
                    if user in review.owners or user.getPreference(db, "review.dropAnyReview"):
                        target.button(id="dropReview", onclick="dropReview();").text("Drop Review")

                if user in review.owners and not review.description:
                    target.button(id="writeDescription", onclick="editDescription();").text("Write Description")
            else:
                target.button(id="reopenReview", onclick="reopenReview();").text("Reopen Review")

        target.span("buttonscope buttonscope-global")

    profiler.check("prologue")

    page.utils.generateHeader(body, db, user, renderHeaderItems, profiler=profiler)

    cursor.execute("SELECT 1 FROM fullreviewuserfiles WHERE review=%s AND state='pending' AND assignee=%s", (review.id, user.id))
    hasPendingChanges = bool(cursor.fetchone())

    if hasPendingChanges:
        head.setLink("next", "showcommit?review=%d&filter=pending" % review.id)

    profiler.check("header")

    document.addExternalStylesheet("resource/showreview.css")
    document.addExternalStylesheet("resource/review.css")
    document.addExternalStylesheet("resource/comment.css")
    document.addExternalScript("resource/showreview.js")
    document.addExternalScript("resource/review.js")
    document.addExternalScript("resource/comment.js")
    document.addExternalScript("resource/reviewfilters.js")
    document.addExternalScript("resource/autocomplete.js")
    document.addInternalScript(user.getJS())
    document.addInternalScript("var owners = [ %s ];" % ", ".join(owner.getJSConstructor() for owner in review.owners))
    document.addInternalScript("var updateCheckInterval = %d;" % user.getPreference(db, "review.updateCheckInterval"));

    log.html.addResources(document)

    document.addInternalScript(review.getJS())

    target = body.div("main")

    basic = target.table('paleyellow basic', align='center')
    basic.col(width='10%')
    basic.col(width='60%')
    basic.col(width='30%')
    h1 = basic.tr().td('h1', colspan=3).h1()
    h1.text("r/%d: " % review.id)
    h1.span(id="summary").text("%s" % review.summary, linkify=linkify.Context(db=db, review=review))
    h1.a("edit", href="javascript:editSummary();").text("[edit]")

    def linkToCommit(commit):
        cursor.execute("SELECT 1 FROM commits JOIN changesets ON (child=commits.id) JOIN reviewchangesets ON (changeset=changesets.id) WHERE sha1=%s AND review=%s", (commit.sha1, review.id))
        if cursor.fetchone():
            return "%s/%s?review=%d" % (review.repository.name, commit.sha1, review.id)
        return "%s/%s" % (review.repository.name, commit.sha1)

    def row(heading, value, help, right=None, linkify=False, cellId=None):
        main_row = basic.tr('line')
        main_row.td('heading').text("%s:" % heading)
        if right is False: colspan = 2
        else: colspan = None
        if callable(value): value(main_row.td('value', id=cellId, colspan=colspan).preformatted())
        else: main_row.td('value', id=cellId, colspan=colspan).preformatted().text(value, linkify=linkify, repository=review.repository)
        if right is False: pass
        elif callable(right): right(main_row.td('right', valign='bottom'))
        else: main_row.td('right').text()
        if help: basic.tr('help').td('help', colspan=3).text(help)

    def renderBranchName(target):
        target.code("branch inset").text(review.branch.name, linkify=linkify.Context())

        if repository.name != user.getPreference(db, "defaultRepository"):
            target.text(" in ")
            target.code("repository inset").text(repository.getURL(db, user))

        cursor.execute("""SELECT id, remote, remote_name, disabled, previous
                            FROM trackedbranches
                           WHERE repository=%s
                             AND local_name=%s""",
                       (repository.id, review.branch.name))

        row = cursor.fetchone()
        if row:
            trackedbranch_id, remote, remote_name, disabled, previous = row

            target.p("tracking disabled" if disabled else "tracking").text("tracking")

            target.code("branch inset").text(remote_name, linkify=linkify.Context(remote=remote))
            target.text(" in ")
            target.code("repository inset").text(remote, linkify=linkify.Context())

            if previous:
                target.span("lastupdate").script(type="text/javascript").text("document.write('(last fetched: ' + shortDate(new Date(%d)) + ')');" % (calendar.timegm(previous.utctimetuple()) * 1000))

            if user in review.owners or user.hasRole(db, "administrator"):
                buttons = target.div("buttons")

                if review.state == "open":
                    if disabled:
                        button = buttons.button("enabletracking",
                                                onclick=("enableTracking(%d, %s, %s);"
                                                         % (trackedbranch_id,
                                                            htmlutils.jsify(remote),
                                                            htmlutils.jsify(remote_name))))
                        button.text("Enable Tracking")
                    else:
                        buttons.button("disabletracking", onclick="triggerUpdate(%d);" % trackedbranch_id).text("Update Now")
                        buttons.button("disabletracking", onclick="disableTracking(%d);" % trackedbranch_id).text("Disable Tracking")

                    buttons.button("rebasereview", onclick="location.assign('/rebasetrackingreview?review=%d');" % review.id).text("Rebase Review")

    def renderReviewers(target):
        if review.reviewers:
            for index, reviewer in enumerate(review.reviewers):
                if index != 0: target.text(", ")
                span = target.span("user %s" % reviewer.status)
                span.span("name").text(reviewer.fullname)
                if reviewer.status == 'absent':
                    span.span("status").text(" (%s)" % reviewer.getAbsence(db))
                elif reviewer.status == 'retired':
                    span.span("status").text(" (retired)")
        else:
            target.i().text("No reviewers.")

        cursor.execute("""SELECT reviewfilters.id, reviewfilters.uid, reviewfilters.path
                            FROM reviewfilters
                            JOIN users ON (reviewfilters.uid=users.id)
                           WHERE reviewfilters.review=%s
                             AND reviewfilters.type='reviewer'
                             AND users.status!='retired'""",
                       (review.id,))

        rows = cursor.fetchall()
        reviewer_filters_hidden = []

        if rows:
            table = target.table("reviewfilters reviewers")

            row = table.thead().tr("h1")
            row.th("h1", colspan=4).text("Custom filters:")

            filter_data = {}
            reviewfilters = {}

            for filter_id, user_id, path in rows:
                filter_user = dbutils.User.fromId(db, user_id)
                path = path or '/'
                reviewfilters.setdefault(filter_user.fullname, []).append(path)
                filter_data[(filter_user.fullname, path)] = (filter_id, filter_user)

            count = 0
            tbody = table.tbody()

            for fullname in sorted(reviewfilters.keys()):
                original_paths = sorted(reviewfilters[fullname])
                trimmed_paths = diff.File.eliminateCommonPrefixes(original_paths[:])

                first = True

                for original_path, trimmed_path in zip(original_paths, trimmed_paths):
                    row = tbody.tr("filter")

                    if first:
                        row.td("username", rowspan=len(original_paths)).text(fullname)
                        row.td("reviews", rowspan=len(original_paths)).text("reviews")
                        first = False

                    row.td("path").span().innerHTML(trimmed_path)

                    filter_id, filter_user = filter_data[(fullname, original_path)]

                    href = "javascript:removeReviewFilter(%d, %s, 'reviewer', %s, %s);" % (filter_id, filter_user.getJSConstructor(), htmlutils.jsify(original_path), "true" if filter_user != user else "false")
                    row.td("remove").a(href=href).text("[remove]")

                    count += 1

            tfoot = table.tfoot()
            tfoot.tr().td(colspan=4).text("%d line%s hidden" % (count, "s" if count > 1 else ""))

            if count > 10:
                tbody.setAttribute("class", "hidden")
                reviewer_filters_hidden.append(True)
            else:
                tfoot.setAttribute("class", "hidden")
                reviewer_filters_hidden.append(False)

        buttons = target.div("buttons")

        if reviewer_filters_hidden:
            buttons.button("showfilters", onclick="toggleReviewFilters('reviewers', $(this));").text("%s Custom Filters" % ("Show" if reviewer_filters_hidden[0] else "Hide"))

        if not review.applyfilters:
            buttons.button("applyfilters", onclick="applyFilters('global');").text("Apply Global Filters")

        if review.applyfilters and review.repository.parent and not review.applyparentfilters:
            buttons.button("applyparentfilters", onclick="applyFilters('upstream');").text("Apply Upstream Filters")

        buttons.button("addreviewer", onclick="addReviewer();").text("Add Reviewer")
        buttons.button("manage", onclick="location.href='managereviewers?review=%d';" % review.id).text("Manage Assignments")

    def renderWatchers(target):
        if review.watchers:
            for index, watcher in enumerate(review.watchers):
                if index != 0: target.text(", ")
                span = target.span("user %s" % watcher.status)
                span.span("name").text(watcher.fullname)
                if watcher.status == 'absent':
                    span.span("status").text(" (%s)" % watcher.getAbsence(db))
                elif watcher.status == 'retired':
                    span.span("status").text(" (retired)")
        else:
            target.i().text("No watchers.")

        cursor.execute("""SELECT reviewfilters.id, reviewfilters.uid, reviewfilters.path
                            FROM reviewfilters
                            JOIN users ON (reviewfilters.uid=users.id)
                           WHERE reviewfilters.review=%s
                             AND reviewfilters.type='watcher'
                             AND users.status!='retired'""",
                       (review.id,))

        rows = cursor.fetchall()
        watcher_filters_hidden = []

        if rows:
            table = target.table("reviewfilters watchers")

            row = table.thead().tr("h1")
            row.th("h1", colspan=4).text("Custom filters:")

            filter_data = {}
            reviewfilters = {}

            for filter_id, user_id, path in rows:
                filter_user = dbutils.User.fromId(db, user_id)
                path = path or '/'
                reviewfilters.setdefault(filter_user.fullname, []).append(path)
                filter_data[(filter_user.fullname, path)] = (filter_id, filter_user)

            count = 0
            tbody = table.tbody()

            for fullname in sorted(reviewfilters.keys()):
                original_paths = sorted(reviewfilters[fullname])
                trimmed_paths = diff.File.eliminateCommonPrefixes(original_paths[:])

                first = True

                for original_path, trimmed_path in zip(original_paths, trimmed_paths):
                    row = tbody.tr("filter")

                    if first:
                        row.td("username", rowspan=len(original_paths)).text(fullname)
                        row.td("reviews", rowspan=len(original_paths)).text("watches")
                        first = False

                    row.td("path").span().innerHTML(trimmed_path)

                    filter_id, filter_user = filter_data[(fullname, original_path)]

                    href = "javascript:removeReviewFilter(%d, %s, 'watcher', %s, %s);" % (filter_id, filter_user.getJSConstructor(), htmlutils.jsify(original_path), "true" if filter_user != user else "false")
                    row.td("remove").a(href=href).text("[remove]")

                    count += 1

            tfoot = table.tfoot()
            tfoot.tr().td(colspan=4).text("%d line%s hidden" % (count, "s" if count > 1 else ""))

            if count > 10:
                tbody.setAttribute("class", "hidden")
                watcher_filters_hidden.append(True)
            else:
                tfoot.setAttribute("class", "hidden")
                watcher_filters_hidden.append(False)

        buttons = target.div("buttons")

        if watcher_filters_hidden:
            buttons.button("showfilters", onclick="toggleReviewFilters('watchers', $(this));").text("%s Custom Filters" % ("Show" if watcher_filters_hidden[0] else "Hide"))

        buttons.button("addwatcher", onclick="addWatcher();").text("Add Watcher")

        if user not in review.reviewers and user not in review.owners:
            if user not in review.watchers:
                buttons.button("watch", onclick="watchReview();").text("Watch Review")
            elif review.watchers[user] == "manual":
                buttons.button("watch", onclick="unwatchReview();").text("Stop Watching Review")

    def renderEditOwners(target):
        target.button("description", onclick="editOwners();").text("Edit Owners")

    def renderEditDescription(target):
        target.button("description", onclick="editDescription();").text("Edit Description")

    def renderRecipientList(target):
        cursor.execute("""SELECT uid, fullname, include
                            FROM reviewrecipientfilters
                 LEFT OUTER JOIN users ON (uid=id)
                           WHERE review=%s""",
                       (review.id,))

        default_include = True
        included = dict((owner.fullname, owner.id) for owner in review.owners)
        excluded = {}

        for user_id, fullname, include in cursor:
            if user_id is None: default_include = include
            elif include: included[fullname] = user_id
            elif user_id not in review.owners: excluded[fullname] = user_id

        mode = None
        users = None

        buttons = []
        opt_in_button = False
        opt_out_button = False

        if default_include:
            if excluded:
                mode = "Everyone except "
                users = excluded
                opt_out_button = user.fullname not in excluded
                opt_in_button = not opt_out_button
            else:
                mode = "Everyone."
                opt_out_button = True
        else:
            if included:
                mode = "No-one except "
                users = included
                opt_in_button = user.fullname not in included
                opt_out_button = not opt_in_button
            else:
                mode = "No-one at all."
                opt_in_button = True

        if user not in review.owners and (user in review.reviewers or user in review.watchers):
            if opt_in_button:
                buttons.append(("Include me, please!", "includeRecipient(%d);" % user.id))
            if opt_out_button:
                buttons.append(("Exclude me, please!", "excludeRecipient(%d);" % user.id))

        target.span("mode").text(mode)

        if users:
            container = target.span("users")

            first = True
            for fullname in sorted(users.keys()):
                if first: first = False
                else: container.text(", ")

                container.span("user", critic_user_id=users[fullname]).text(fullname)

            container.text(".")

        if buttons:
            container = target.div("buttons")

            for label, onclick in buttons:
                container.button(onclick=onclick).text(label)

    row("Branch", renderBranchName, "The branch containing the commits to review.", right=False)
    row("Owner%s" % ("s" if len(review.owners) > 1 else ""), ", ".join(owner.fullname for owner in review.owners), "The users who created and/or owns the review.", right=renderEditOwners)
    if review.description:
        row("Description", review.description, "A longer description of the changes to be reviewed.", linkify=linkToCommit, cellId="description", right=renderEditDescription)
    row("Reviewers", renderReviewers, "Users responsible for reviewing the changes in this review.", right=False)
    row("Watchers", renderWatchers, "Additional users who receive e-mails about updates to this review.", right=False)
    row("Recipient List", renderRecipientList, "Users (among the reviewers and watchers) who will receive any e-mails about the review.", right=False)

    profiler.check("basic")

    review_state = review.getReviewState(db)

    profiler.check("review state")

    progress = target.table('paleyellow progress', align='center')
    progress_header = progress.tr().td('h1', colspan=3).h1()
    progress_header.text("Review Progress")
    progress_header_right = progress_header.span("right")
    progress_header_right.text("Display log: ")
    progress_header_right.a(href="showreviewlog?review=%d&granularity=module" % review.id).text("[per module]")
    progress_header_right.text()
    progress_header_right.a(href="showreviewlog?review=%d&granularity=file" % review.id).text("[per file]")
    progress_h1 = progress.tr().td('percent', colspan=3).h1()

    title_data = { 'id': 'r/%d' % review.id,
                   'summary': review.summary,
                   'progress': str(review_state) }

    if review.state == "closed":
        progress_h1.img(src=htmlutils.getStaticResourceURI("seal-of-approval-left.png"),
                        style="position: absolute; margin-left: -80px; margin-top: -100px")
        progress_h1.text("Finished!")

        if review.repository.hasMainBranch():
            main_branch = review.repository.getMainBranch(db)
            if review.branch.getHead(db).isAncestorOf(main_branch.getHead(db)):
                remark = progress_h1.div().span("remark")
                remark.text("Merged to ")
                remark.a(href="/log?repository=%s&branch=%s" % (review.repository.name, main_branch.name)).text(main_branch.name)
                remark.text(".")
    elif review.state == "dropped":
        progress_h1.text("Dropped...")
    elif review.state == "open" and review_state.accepted:
        progress_h1.img(src=htmlutils.getStaticResourceURI("seal-of-approval-left.png"),
                        style="position: absolute; margin-left: -80px; margin-top: -100px")
        progress_h1.text("Accepted!")
        progress_h1.div().span("remark").text("Hurry up and close it before anyone has a change of heart.")
    else:
        progress_h1.text(review_state.getProgress())

        if review_state.issues:
            progress_h1.span("comments").text(" and ")
            progress_h1.text("%d" % review_state.issues)
            progress_h1.span("comments").text(" issue%s" % (review_state.issues > 1 and "s" or ""))

        if review_state.getPercentReviewed() != 100.0:
            cursor = db.cursor()
            cursor.execute("""SELECT 1
                                FROM reviewfiles
                     LEFT OUTER JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                               WHERE reviewfiles.review=%s
                                 AND reviewfiles.state='pending'
                                 AND reviewuserfiles.uid IS NULL""",
                           (review.id,))

            if cursor.fetchone():
                progress.tr().td('stuck', colspan=3).a(href="showreviewlog?review=%d&granularity=file&unassigned=yes" % review.id).text("Not all changes have a reviewer assigned!")

            cursor.execute("""SELECT uid, MIN(reviewuserfiles.time)
                                FROM reviewfiles
                                JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                               WHERE reviewfiles.review=%s
                                 AND reviewfiles.state='pending'
                            GROUP BY reviewuserfiles.uid""",
                           (review.id,))

            def total_seconds(delta):
                return delta.days * 60 * 60 * 24 + delta.seconds

            now = datetime.datetime.now()
            pending_reviewers = [(dbutils.User.fromId(db, user_id), total_seconds(now - timestamp)) for (user_id, timestamp) in cursor.fetchall() if total_seconds(now - timestamp) > 60 * 60 * 8]

            if pending_reviewers:
                progress.tr().td('stragglers', colspan=3).text("Needs review from")
                for reviewer, seconds in pending_reviewers:
                    if reviewer.status == 'retired': continue
                    elif reviewer.status == 'absent': warning = " absent"
                    elif not reviewer.getPreference(db, "email.activated"): warning = " no-email"
                    else: warning = ""

                    if seconds < 60 * 60 * 24:
                        hours = seconds / (60 * 60)
                        duration = " (%d hour%s)" % (hours, "s" if hours > 1 else "")
                    elif seconds < 60 * 60 * 24 * 7:
                        days = seconds / (60 * 60 * 24)
                        duration = " (%d day%s)" % (days, "s" if days > 1 else "")
                    elif seconds < 60 * 60 * 24 * 30:
                        weeks = seconds / (60 * 60 * 24 * 7)
                        duration = " (%d week%s)" % (weeks, "s" if weeks > 1 else "")
                    else:
                        duration = " (wake up!)"

                    progress.tr().td('straggler' + warning, colspan=3).text("%s%s" % (reviewer.fullname, duration))
                if user in review.owners:
                    progress.tr().td('pinging', colspan=3).span().text("Send a message to these users by pinging the review.")

    title_format = user.getPreference(db, 'ui.title.showReview')

    try:
        document.setTitle(title_format % title_data)
    except Exception as exc:
        document.setTitle(traceback.format_exception_only(type(exc), exc)[0].strip())

    profiler.check("progress")

    check = profiler.start("ApprovalColumn.fillCache")

    def linkToCommit(commit, overrides={}):
        if "rebase_conflicts" in overrides:
            return "%s..%s?review=%d&conflicts=yes" % (overrides["rebase_conflicts"].sha1[:8], commit.sha1[:8], review.id)
        else:
            return "%s?review=%d" % (commit.sha1[:8], review.id)

    approval_cache = {}

    ApprovalColumn.fillCache(db, user, review, approval_cache, profiler)

    check.stop()

    summary_column = SummaryColumn(review, linkToCommit)
    summary_column.fillCache(db, review)

    profiler.check("SummaryColumn.fillCache")

    columns = [(10, log.html.WhenColumn()),
               (60, summary_column),
               (16, log.html.AuthorColumn()),
               (7, ApprovalColumn(user, review, ApprovalColumn.APPROVED, approval_cache)),
               (7, ApprovalColumn(user, review, ApprovalColumn.TOTAL, approval_cache))]

    def renderReviewPending(db, target):
        if not user.isAnonymous():
            target.text("Filter: ")

            if hasPendingChanges:
                target.a(href="showcommit?review=%d&filter=pending" % review.id, title="All changes you need to review.").text("[pending]")
                target.text()
            if user in review.reviewers:
                target.a(href="showcommit?review=%d&filter=reviewable" % review.id, title="All changes you can review, including what you've already reviewed.").text("[reviewable]")
                target.text()

            target.a(href="showcommit?review=%d&filter=relevant" % review.id, title="All changes that match your filters.").text("[relevant]")
            target.text()

        target.text("Manual: ")
        target.a(href="filterchanges?review=%d" % review.id, title="Manually select what files to display of the changes from all commits.").text("[full]")
        target.text()
        target.a(href="javascript:void(filterPartialChanges());", title="Manually select what files to display of the changes in a selection of commits.").text("[partial]")

    req.addResponseHeader("ETag", review.getETag(db, user))

    if user.getPreference(db, "review.useMustRevalidate"):
        req.addResponseHeader("Cache-Control", "must-revalidate")

    yield flush(target)

    try:
        if prefetch_commits.error is not None:
            raise base.ImplementationError(
                "failed to prefetch commits:\n%s" % prefetch_commits.error)

        prefetch_commits.getCommits(db)

        profiler.check("FetchCommits.getCommits()")

        cursor.execute("""SELECT DISTINCT type, parent, child
                            FROM changesets
                            JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                            JOIN commits ON (commits.id=changesets.child)
                           WHERE review=%s""",
                       (review.id,))

        commits = set()
        conflicts = {}

        for changeset_type, parent_id, child_id in cursor:
            child = gitutils.Commit.fromId(db, repository, child_id)
            if changeset_type == "conflicts":
                conflicts[child] = gitutils.Commit.fromId(db, repository, parent_id)
            else:
                commits.add(child)

        commits = list(commits)

        cursor.execute("""SELECT id, old_head, new_head, new_upstream, uid, branch
                            FROM reviewrebases
                           WHERE review=%s""",
                       (review.id,))

        all_rebases = [(rebase_id,
                        gitutils.Commit.fromId(db, repository, old_head),
                        gitutils.Commit.fromId(db, repository, new_head) if new_head else None,
                        dbutils.User.fromId(db, user_id),
                        gitutils.Commit.fromId(db, repository, new_upstream) if new_upstream is not None else None,
                        branch_name)
                       for rebase_id, old_head, new_head, new_upstream, user_id, branch_name in cursor]

        bottom_right = None

        finished_rebases = filter(lambda item: item[2] is not None, all_rebases)
        current_rebases = filter(lambda item: item[2] is None, all_rebases)

        if current_rebases:
            assert len(current_rebases) == 1

            def renderCancelRebase(db, target):
                target.button("cancelrebase").text("Cancel Rebase")

            if user == current_rebases[0][3]:
                bottom_right = renderCancelRebase
        else:
            def renderPrepareRebase(db, target):
                target.button("preparerebase").text("Prepare Rebase")

            bottom_right = renderPrepareRebase

        if finished_rebases:
            cursor.execute("""SELECT commit
                                FROM reachable
                               WHERE branch=%s""",
                           (review.branch.id,))

            actual_commits = [gitutils.Commit.fromId(db, repository, commit_id) for (commit_id,) in cursor]
        else:
            actual_commits = []

        log.html.render(db, target, "Commits (%d)", commits=commits, columns=columns, title_right=renderReviewPending, rebases=finished_rebases, branch_name=review.branch.name, bottom_right=bottom_right, review=review, highlight=highlight, profiler=profiler, user=user, extra_commits=actual_commits, conflicts=conflicts)

        yield flush(target)

        profiler.check("log")
    except gitutils.GitReferenceError as error:
        div = target.div("error")
        div.h1().text("Error!")
        div.text("The commit %s is missing from the repository." % error.sha1)
    except gitutils.GitError as error:
        div = target.div("error")
        div.h1().text("Error!")
        div.text("Failed to read commits from the repository: %s" % error.message)

    all_chains = review_comment.CommentChain.fromReview(db, review, user)

    profiler.check("chains (load)")

    if all_chains:
        issue_chains = filter(lambda chain: chain.type == "issue", all_chains)
        draft_issues = filter(lambda chain: chain.state == "draft", issue_chains)
        open_issues = filter(lambda chain: chain.state == "open", issue_chains)
        addressed_issues = filter(lambda chain: chain.state == "addressed", issue_chains)
        closed_issues = filter(lambda chain: chain.state == "closed", issue_chains)
        note_chains = filter(lambda chain: chain.type == "note", all_chains)
        draft_notes = filter(lambda chain: chain.state == "draft", note_chains)
        open_notes = filter(lambda chain: chain.state != "draft" and chain.state != "empty", note_chains)
    else:
        open_issues = []
        open_notes = []

    chains = target.table("paleyellow comments", align="center", cellspacing=0)
    h1 = chains.tr("h1").td("h1", colspan=3).h1().text("Comments")
    links = h1.span("links")

    if all_chains:
        links.a(href="showcomments?review=%d&filter=all" % review.id).text("[display all]")

        if not user.isAnonymous():
            links.a(href="showcomments?review=%d&filter=all&blame=%s" % (review.id, user.name)).text("[in my commits]")

            cursor.execute("""SELECT count(commentstoread.comment) > 0
                                FROM commentchains
                                JOIN comments ON (comments.chain=commentchains.id)
                                JOIN commentstoread ON (commentstoread.comment=comments.id)
                               WHERE commentchains.review=%s
                                 AND commentstoread.uid=%s""",
                           [review.id, user.id])

            if cursor.fetchone()[0]:
                links.a(href="showcomments?review=%d&filter=toread" % review.id).text("[display unread]")

        def renderChains(target, chains):
            for chain in chains:
                row = target.tr("comment %s %s" % (chain.type, chain.state))
                row.td("author").text(chain.user.fullname)
                row.td("title").a(href="showcomment?chain=%d" % chain.id).innerHTML(chain.leader())

                ncomments = chain.countComments()
                nunread = chain.countUnread()

                cell = row.td("when")
                if ncomments == 1:
                    if nunread: cell.b().text("Unread")
                    else: cell.text("No replies")
                else:
                    if nunread: cell.b().text("%d of %d unread" % (nunread, ncomments))
                    else: cell.text("%d repl%s" % (ncomments - 1, "ies" if ncomments > 2 else "y"))

        if draft_issues:
            h2 = chains.tr("h2", id="draft-issues").td("h2", colspan=3).h2().text("Draft Issues")
            h2.a(href="showcomments?review=%d&filter=draft-issues" % review.id).text("[display all]")
            h2.a(href="showcomments?review=%d&filter=draft-issues&blame=%s" % (review.id, user.name)).text("[in my commits]")
            renderChains(chains, draft_issues)

        if open_issues:
            h2 = chains.tr("h2", id="open-issues").td("h2", colspan=3).h2().text("Open Issues")
            h2.a(href="showcomments?review=%d&filter=open-issues" % review.id).text("[display all]")
            h2.a(href="showcomments?review=%d&filter=open-issues&blame=%s" % (review.id, user.name)).text("[in my commits]")
            renderChains(chains, open_issues)

        if addressed_issues:
            h2 = chains.tr("h2", id="addressed-issues").td("h2", colspan=3).h2().text("Addressed Issues")
            h2.a(href="showcomments?review=%d&filter=addressed-issues" % review.id).text("[display all]")
            h2.a(href="showcomments?review=%d&filter=addressed-issues&blame=%s" % (review.id, user.name)).text("[in my commits]")
            renderChains(chains, addressed_issues)

        if closed_issues:
            h2 = chains.tr("h2", id="closed-issues").td("h2", colspan=3).h2().text("Resolved Issues")
            h2.a(href="showcomments?review=%d&filter=closed-issues" % review.id).text("[display all]")
            h2.a(href="showcomments?review=%d&filter=closed-issues&blame=%s" % (review.id, user.name)).text("[in my commits]")
            renderChains(chains, closed_issues)

        if draft_notes:
            h2 = chains.tr("h2", id="draft-notes").td("h2", colspan=3).h2().text("Draft Notes")
            h2.a(href="showcomments?review=%d&filter=draft-notes" % review.id).text("[display all]")
            h2.a(href="showcomments?review=%d&filter=draft-notes&blame=%s" % (review.id, user.name)).text("[in my commits]")
            renderChains(chains, draft_notes)

        if open_notes:
            h2 = chains.tr("h2", id="notes").td("h2", colspan=3).h2().text("Notes")
            h2.a(href="showcomments?review=%d&filter=open-notes" % review.id).text("[display all]")
            h2.a(href="showcomments?review=%d&filter=open-notes&blame=%s" % (review.id, user.name)).text("[in my commits]")
            renderChains(chains, open_notes)

    buttons = chains.tr("buttons").td("buttons", colspan=3)
    buttons.button(onclick="CommentChain.create('issue');").text("Raise Issue")
    buttons.button(onclick="CommentChain.create('note');").text("Write Note")

    profiler.check("chains (render)")

    yield flush(target)

    cursor.execute("""SELECT DISTINCT reviewfiles.file, theirs.uid
                        FROM reviewfiles
                        JOIN reviewuserfiles AS yours ON (yours.file=reviewfiles.id)
                        JOIN reviewuserfiles AS theirs ON (theirs.file=yours.file AND theirs.uid!=yours.uid)
                       WHERE reviewfiles.review=%s
                         AND yours.uid=%s""",
                   (review.id, user.id))
    rows = cursor.fetchall()

    profiler.check("shared assignments (query)")

    if rows:
        reviewers = {}

        for file_id, user_id in rows:
            reviewers.setdefault(file_id, {})[user_id] = set()

        shared = target.table('paleyellow shared', align='center', cellspacing=0)
        row = shared.tr('h1')
        shared_header = row.td('h1', colspan=2).h1()
        shared_header.text("Shared Assignments")
        shared_buttons = row.td('buttons', colspan=2).span(style="display: none")
        shared_buttons.button("confirm").text("Confirm")
        shared_buttons.button("cancel").text("Cancel")

        granularity = "module"

        def moduleFromFile(file_id):
            filename = dbutils.describe_file(db, file_id)
            return getModuleFromFile(repository, filename) or filename

        def formatFiles(files):
            paths = sorted([dbutils.describe_file(db, file_id) for file_id in files])
            if granularity == "file":
                return diff.File.eliminateCommonPrefixes(paths)
            else:
                modules = set()
                files = []
                for path in paths:
                    module = getModuleFromFile(path)
                    if module: modules.add(module)
                    else: files.append(path)
                return sorted(modules) + diff.File.eliminateCommonPrefixes(files)

        files_per_team = review_utils.collectReviewTeams(reviewers)
        teams_per_modules = {}

        profiler.check("shared assignments (collect teams)")

        for team, files in files_per_team.items():
            modules = set()
            for file_id in files:
                modules.add(moduleFromFile(file_id))
            teams_per_modules.setdefault(frozenset(modules), set()).update(team)

        for modules, team in teams_per_modules.items():
            row = shared.tr("reviewers")

            cell = row.td("reviewers")
            members = sorted([dbutils.User.fromId(db, user_id).fullname for user_id in team])
            for member in members: cell.text(member).br()
            row.td("willreview").innerHTML("<span class='also'>also</span>&nbsp;review&nbsp;changes&nbsp;in")

            cell = row.td("files")
            for path in diff.File.eliminateCommonPrefixes(sorted(modules)):
                cell.span("file").innerHTML(path).br()

            paths = json_encode(list(modules))
            user_ids = json_encode(list(team))

            cell = row.td("buttons")
            cell.button("accept", critic_paths=paths, critic_user_ids=user_ids).text("I will review this!")
            cell.button("deny", critic_paths=paths, critic_user_ids=user_ids).text("They will review this!")

    yield flush(target)

    profiler.check("shared assignments")

    cursor.execute("SELECT batches.id, users.fullname, batches.comment, batches.time FROM batches JOIN users ON (users.id=batches.uid) WHERE batches.review=%s ORDER BY batches.id DESC", [review.id])
    rows = cursor.fetchall()

    if rows:
        notes = dict([(chain.id, chain) for chain in open_notes])

        batches = target.table("paleyellow batches", align="center", cellspacing=0)
        batches.tr().td("h1", colspan=3).h1().text("Work Log")

        for batch_id, user_fullname, chain_id, when in rows:
            row = batches.tr("batch")
            row.td("author").text(user_fullname)
            title = "<i>No comment</i>"
            if chain_id:
                if chain_id in notes:
                    title = notes[chain_id].leader()
                else:
                    for chain in all_chains:
                        if chain.id == chain_id:
                            title = chain.leader()
                            break
            row.td("title").a(href="showbatch?batch=%d" % batch_id).innerHTML(title)
            row.td("when").text(user.formatTimestamp(db, when))

    profiler.check("batches")
    profiler.output(db, user, target)

    yield flush()

    if review.branch.head:
        try: head_according_to_git = repository.revparse(review.branch.name)
        except: head_according_to_git = None

        head_according_to_us = review.branch.head.sha1

        if head_according_to_git != head_according_to_us:
            # The git repository disagrees with us.  Potentially harmful updates
            # to the branch will be rejected by the git hook while this is the
            # case, but this means that "our" head might not be referenced at
            # all and thus that it might be GC:ed by the git repository at some
            # point.  To avoid that, add a keepalive reference.
            repository.keepalive(head_according_to_us)

            yield "\n<!-- branch head mismatch: git=%s, us=%s (corrected) -->" % (head_according_to_git[:8] if head_according_to_git else "N/A", head_according_to_us[:8])
