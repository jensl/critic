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

import dbutils
import gitutils
import htmlutils
import profiling
import page.utils
import auth

def renderDashboard(req, db, user):
    if user.isAnonymous(): default_show = "open"
    else: default_show = user.getPreference(db, "dashboard.defaultGroups")

    show = req.getParameter("show", default_show)

    if user.isAnonymous():
        def possible(group):
            return group in ("open", "closed")
    else:
        def possible(group):
            return True

    showlist = filter(possible, show.split(","))
    showset = set(showlist)

    if user.getPreference(db, "commit.diff.compactMode"): default_compact = "yes"
    else: default_compact = "no"

    repository_arg = req.getParameter("repository", None)
    repository = gitutils.Repository.fromParameter(db, repository_arg) if repository_arg else None
    compact = req.getParameter("compact", default_compact) == "yes"

    cursor = db.cursor()

    profiler = profiling.Profiler()
    document = htmlutils.Document(req)

    document.setTitle("Dashboard")

    html = document.html()
    head = html.head()
    body = html.body()

    def generateRight(target):
        def addLink(key, title=None):
            if not title: title = key
            if key not in showset:
                target.text("[")
                target.a(href="dashboard?show=%s" % ",".join(showlist + [key])).text("show %s" % title)
                target.text("]")

        if user.isAnonymous():
            addLink("open", "open")
            addLink("closed")
        else:
            target.text("[")
            target.a(href="config?highlight=dashboard.defaultGroups").text("configure defaults")
            target.text("]")

            addLink("owned")
            addLink("draft")
            addLink("active")
            addLink("watched")
            addLink("open", "other open")
            addLink("closed")

    page.utils.generateHeader(body, db, user, current_page="dashboard", generate_right=generateRight, profiler=profiler)

    document.addExternalStylesheet("resource/dashboard.css")
    document.addExternalScript("resource/dashboard.js")
    document.addInternalScript(user.getJS())

    target = body.div("main")

    def flush(target):
        return document.render(stop=target, pretty=not compact)

    def includeReview(review_id):
        if repository:
            cursor = db.cursor()
            cursor.execute("SELECT branches.repository FROM branches JOIN reviews ON (reviews.branch=branches.id) WHERE reviews.id=%s", (review_id,))
            return cursor.fetchone()[0] == repository.id
        else:
            return True

    def sortedReviews(data):
        reviews = []
        for review_id in sorted(data.keys()):
            reviews.append((review_id, data[review_id]))
        return reviews

    def isAccepted(review_ids):
        cursor.execute("""SELECT reviews.id, COUNT(reviewfiles.id)=0 AND COUNT(commentchains.id)=0
                            FROM reviews
                 LEFT OUTER JOIN reviewfiles ON (reviewfiles.review=reviews.id
                                             AND reviewfiles.state='pending')
                 LEFT OUTER JOIN commentchains ON (commentchains.review=reviews.id
                                               AND commentchains.type='issue'
                                               AND commentchains.state='open')
                           WHERE reviews.id=ANY (%s)
                        GROUP BY reviews.id""",
                       (review_ids,))

        return dict(cursor)

    checked_repositories = {}
    def accessRepository(repository_id):
        already_checked = checked_repositories.get(repository_id)
        if already_checked is not None:
            return already_checked
        is_allowed = auth.AccessControlProfile.isAllowedRepository(
            db.profiles, "read", repository_id)
        checked_repositories[repository_id] = is_allowed
        return is_allowed

    def renderReviews(target, reviews, lines_and_comments=True, links=True):
        cursor.execute("SELECT id, repository, name FROM branches WHERE id=ANY (%s)",
                       (list(branch_id for _, (_, branch_id, _, _) in reviews),))

        branch_data = { branch_id: (repository_id, name)
                        for branch_id, repository_id, name in cursor }

        for review_id, (summary, branch_id, lines, comments) in reviews:
            repository_id, branch_name = branch_data[branch_id]
            if not accessRepository(repository_id):
                continue
            row = target.tr("review")
            row.td("name").text(branch_name)
            row.td("title").a(href="r/%d" % review_id).text(summary)

            if lines_and_comments:
                if lines:
                    if links:
                        row.td("lines").a(href="showcommit?review=%d&filter=pending" % review_id).text("%d lines" % (sum(lines)))
                    else:
                        row.td("lines").text("%d lines" % (sum(lines)))
                else: row.td("lines").text()
                if comments:
                    if links:
                        row.td("comments").a(href="showcomments?review=%s&filter=toread" % review_id).text("%d comment%s" % (comments, "s" if comments > 1 else ""))
                    else:
                        row.td("comments").text("%d comment%s" % (comments, "s" if comments > 1 else ""))
                else: row.td("comments").text()

    def hidden(what):
        new_show = ",".join(filter(lambda item: item != what, showlist))
        if new_show: return "dashboard?show=%s" % new_show
        else: return "dashboard"

    profiler.check("generate: prologue")

    def renderOwned():
        owned_accepted = []
        owned_open = []

        cursor.execute("""SELECT id, summary, branch
                            FROM reviews
                            JOIN reviewusers ON (review=id AND reviewusers.owner)
                           WHERE state='open'
                             AND uid=%s
                        ORDER BY id DESC""",
                       (user.id,))

        owned = cursor.fetchall()

        profiler.check("query: owned")

        is_accepted = isAccepted(list(review_id for review_id, _, _ in owned))

        for review_id, summary, branch_id in owned:
            if includeReview(review_id):
                if is_accepted[review_id]:
                    owned_accepted.append((review_id, (summary, branch_id, None, None)))
                else:
                    owned_open.append((review_id, (summary, branch_id, None, None)))

        profiler.check("processing: owned")

        if owned_accepted or owned_open:
            table = target.table("paleyellow reviews", id="owned", align="center", cellspacing=0)
            table.col(width="15%")
            table.col(width="55%")
            table.col(width="15%")
            table.col(width="15%")
            header = table.tr().td("h1", colspan=4).h1()
            header.text("Owned By You")
            header.span("right").a(href=hidden("owned")).text("[hide]")

            if owned_accepted:
                table.tr(id="accepted").td("h2", colspan=4).h2().text("Accepted")
                renderReviews(table, owned_accepted)

            if owned_open:
                table.tr(id="open").td("h2", colspan=4).h2().text("Pending")
                renderReviews(table, owned_open)

            profiler.check("generate: owned")
            return True

    def renderDraft():
        draft_changes = {}
        draft_comments = {}
        draft_both = {}

        cursor.execute("""SELECT reviews.id, reviews.summary, reviews.branch, SUM(reviewfiles.deleted), SUM(reviewfiles.inserted)
                            FROM reviews
                            JOIN reviewfiles ON (reviewfiles.review=reviews.id)
                            JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)
                           WHERE reviews.state='open'
                             AND reviewfiles.state=reviewfilechanges.from_state
                             AND reviewfilechanges.state='draft'
                             AND reviewfilechanges.uid=%s
                        GROUP BY reviews.id, reviews.summary, reviews.branch""",
                       (user.id,))

        profiler.check("query: draft lines")

        for review_id, summary, branch_id, deleted_count, inserted_count in cursor:
            if includeReview(review_id):
                draft_changes[review_id] = (summary, branch_id, (deleted_count, inserted_count), None)

        profiler.check("processing: draft lines")

        cursor.execute("""SELECT reviews.id, reviews.summary, reviews.branch, COUNT(comments.id)
                            FROM reviews
                            JOIN commentchains ON (commentchains.review=reviews.id)
                            JOIN comments ON (comments.chain=commentchains.id)
                           WHERE comments.state='draft'
                             AND comments.uid=%s
                        GROUP BY reviews.id, reviews.summary, reviews.branch""",
                       [user.id])

        profiler.check("query: draft comments")

        for review_id, summary, branch_id, comments_count in cursor:
            if includeReview(review_id):
                if draft_changes.has_key(review_id):
                    draft_both[review_id] = (summary, branch_id, draft_changes[review_id][2], comments_count)
                    del draft_changes[review_id]
                else:
                    draft_comments[review_id] = (summary, branch_id, None, comments_count)

        profiler.check("processing: draft comments")

        if draft_both or draft_changes or draft_comments:
            table = target.table("paleyellow reviews", id="draft", align="center", cellspacing=0)
            table.col(width="15%")
            table.col(width="55%")
            table.col(width="15%")
            table.col(width="15%")
            header = table.tr().td("h1", colspan=4).h1()
            header.text("Reviews With Unsubmitted Work")
            header.span("right").a(href=hidden("draft")).text("[hide]")

            if draft_both:
                table.tr(id="draft-changes-comments").td("h2", colspan=4).h2().text("Draft Changes And Comments")
                renderReviews(table, sortedReviews(draft_both), links=False)

            if draft_changes:
                table.tr(id="draft-changes").td("h2", colspan=4).h2().text("Draft Changes")
                renderReviews(table, sortedReviews(draft_changes), links=False)

            if draft_comments:
                table.tr(id="draft-comments").td("h2", colspan=4).h2().text("Draft Comments")
                renderReviews(table, sortedReviews(draft_comments), links=False)

            profiler.check("generate: draft")
            return True

    active = {}

    def fetchActive():
        if not active:
            with_changes = {}
            with_comments = {}
            with_both = {}

            cursor.execute("""SELECT reviews.id, reviews.summary, reviews.branch, SUM(reviewfiles.deleted), SUM(reviewfiles.inserted)
                                FROM reviews
                                JOIN reviewusers ON (reviewusers.review=reviews.id
                                                 AND reviewusers.uid=%s)
                                JOIN reviewfiles ON (reviewfiles.review=reviews.id)
                                JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id
                                                     AND reviewuserfiles.uid=%s)
                               WHERE reviews.state='open'
                                 AND reviewfiles.state='pending'
                            GROUP BY reviews.id, reviews.summary, reviews.branch""",
                           (user.id, user.id))

            profiler.check("query: active lines")

            for review_id, summary, branch_id, deleted_count, inserted_count in cursor:
                if includeReview(review_id):
                    with_changes[review_id] = (summary, branch_id, (deleted_count, inserted_count), None)

            profiler.check("processing: active lines")

            cursor.execute("""SELECT reviews.id, reviews.summary, reviews.branch, unread.count
                                FROM (SELECT commentchains.review AS review, COUNT(commentstoread.comment) AS count
                                        FROM commentchains
                                        JOIN comments ON (comments.chain=commentchains.id)
                                        JOIN commentstoread ON (commentstoread.comment=comments.id
                                                            AND commentstoread.uid=%s)
                                    GROUP BY commentchains.review) AS unread
                                JOIN reviews ON (reviews.id=unread.review)
                               WHERE reviews.state='open'""",
                           (user.id,))

            profiler.check("query: active comments")

            for review_id, summary, branch_id, comments_count in cursor:
                if includeReview(review_id):
                    if with_changes.has_key(review_id):
                        with_both[review_id] = (summary, branch_id, with_changes[review_id][2], comments_count)
                        del with_changes[review_id]
                    else:
                        with_comments[review_id] = (summary, branch_id, None, comments_count)

            profiler.check("processing: active comments")

            active["changes"] = with_changes
            active["comments"] = with_comments
            active["both"] = with_both

    def renderActive():
        fetchActive()

        if active["both"] or active["changes"] or active["comments"]:
            table = target.table("paleyellow reviews", id="active", align="center", cellspacing=0)
            table.col(width="15%")
            table.col(width="55%")
            table.col(width="15%")
            table.col(width="15%")
            header = table.tr().td("h1", colspan=4).h1()
            header.text("Active Reviews")
            header.span("right").a(href=hidden("active")).text("[hide]")

            if active["both"]:
                review_ids = ",".join(map(str, active["both"].keys()))
                h2 = table.tr(id="active-changes-comments").td("h2", colspan=4).h2().text("Has Changes And Comments")
                h2.a(href="javascript:void(0);", onclick="markChainsAsRead([%s]);" % review_ids).text("[mark all as read]")
                renderReviews(table, sortedReviews(active["both"]))

            if active["changes"]:
                table.tr(id="active-changes").td("h2", colspan=4).h2().text("Has Changes")
                renderReviews(table, sortedReviews(active["changes"]))

            if active["comments"]:
                review_ids = ",".join(map(str, active["comments"].keys()))
                h2 = table.tr(id="active-comments").td("h2", colspan=4).h2().text("Has Comments")
                h2.a(href="javascript:void(0);", onclick="markChainsAsRead([%s]);" % review_ids).text("[mark all as read]")
                renderReviews(table, sortedReviews(active["comments"]))

            profiler.check("generate: active")
            return True

    other = {}

    def fetchWatchedAndClosed():
        if not other:
            if "watched" not in showset:
                state_filter = " WHERE reviews.state='closed'"
            elif "closed" not in showset:
                state_filter = " WHERE reviews.state='open'"
            else:
                state_filter = ""

            profiler.check("query: watched/closed")

            watched = {}
            owned_closed = {}
            other_closed = {}

            if "watched" in showset: fetchActive()

            cursor.execute("""SELECT reviews.id, reviews.summary, reviews.branch, reviews.state, reviewusers.owner, reviewusers.uid IS NULL
                                FROM reviews
                     LEFT OUTER JOIN reviewusers ON (reviewusers.review=reviews.id AND reviewusers.uid=%s)""" + state_filter,
                           (user.id,))

            for review_id, summary, branch_id, review_state, is_owner, not_associated in cursor:
                if includeReview(review_id):
                    if review_state == 'open':
                        if is_owner or not_associated:
                            continue

                        fetchActive()

                        if active["both"].has_key(review_id) or active["changes"].has_key(review_id) or active["comments"].has_key(review_id):
                            continue

                        watched[review_id] = summary, branch_id, None, None
                    elif is_owner:
                        owned_closed[review_id] = summary, branch_id, None, None
                    else:
                        other_closed[review_id] = summary, branch_id, None, None

            profiler.check("processing: watched/closed")

            other["watched"] = watched
            other["owned-closed"] = owned_closed
            other["other-closed"] = other_closed

    def renderWatched():
        fetchWatchedAndClosed()

        watched = other["watched"]
        accepted = []
        pending = []

        is_accepted = isAccepted(watched.keys())

        for review_id, (summary, branch_id, lines, comments) in sortedReviews(watched):
            if is_accepted[review_id]:
                accepted.append((review_id, (summary, branch_id, lines, comments)))
            else:
                pending.append((review_id, (summary, branch_id, lines, comments)))

        if accepted or pending:
            table = target.table("paleyellow reviews", id="watched", align="center", cellspacing=0)
            table.col(width="30%")
            table.col(width="70%")
            header = table.tr().td("h1", colspan=4).h1()
            header.text("Watched Reviews")
            header.span("right").a(href=hidden("watched")).text("[hide]")

            if accepted:
                table.tr(id="active-changes-comments").td("h2", colspan=4).h2().text("Accepted")
                renderReviews(table, accepted, False)

            if pending:
                table.tr(id="active-changes-comments").td("h2", colspan=4).h2().text("Pending")
                renderReviews(table, pending, False)

            profiler.check("generate: watched")
            return True

    def renderClosed():
        fetchWatchedAndClosed()

        owned_closed = other["owned-closed"]
        other_closed = other["other-closed"]

        if owned_closed or other_closed:
            table = target.table("paleyellow reviews", id="closed", align="center", cellspacing=0)
            table.col(width="30%")
            table.col(width="70%")
            header = table.tr().td("h1", colspan=4).h1()
            header.text("Closed Reviews")
            header.span("right").a(href=hidden("closed")).text("[hide]")

            if not user.isAnonymous():
                if owned_closed:
                    table.tr().td("h2", colspan=4).h2().text("Owned")
                    renderReviews(table, sortedReviews(owned_closed), False)

                if other_closed:
                    table.tr().td("h2", colspan=4).h2().text("Other")
                    renderReviews(table, sortedReviews(other_closed), False)
            else:
                renderReviews(table, sortedReviews(other_closed), False)

            profiler.check("generate: closed")
            return True

    def renderOpen():
        other_open = {}

        cursor.execute("""SELECT reviews.id, reviews.summary, reviews.branch
                            FROM reviews
                 LEFT OUTER JOIN reviewusers ON (reviewusers.review=reviews.id AND reviewusers.uid=%s)
                           WHERE reviews.state='open'
                             AND reviewusers.uid IS NULL""",
                       [user.id])

        profiler.check("query: open")

        for review_id, summary, branch_id in cursor:
            if includeReview(review_id):
                other_open[review_id] = summary, branch_id, None, None

        profiler.check("processing: open")

        if other_open:
            accepted = []
            pending = []

            for review_id, (summary, branch_id, lines, comments) in sortedReviews(other_open):
                if dbutils.Review.isAccepted(db, review_id):
                    accepted.append((review_id, (summary, branch_id, lines, comments)))
                else:
                    pending.append((review_id, (summary, branch_id, lines, comments)))

            table = target.table("paleyellow reviews", id="open", align="center", cellspacing=0)
            table.col(width="30%")
            table.col(width="70%")
            header = table.tr().td("h1", colspan=4).h1()
            header.text("Open Reviews" if user.isAnonymous() else "Other Open Reviews")
            header.span("right").a(href=hidden("open")).text("[hide]")

            if accepted:
                table.tr().td("h2", colspan=4).h2().text("Accepted")
                renderReviews(table, accepted, False)

            if pending:
                table.tr().td("h2", colspan=4).h2().text("Pending")
                renderReviews(table, pending, False)

            profiler.check("generate: open")
            return True

    render = { "owned": renderOwned,
               "draft": renderDraft,
               "active": renderActive,
               "watched": renderWatched,
               "closed": renderClosed,
               "open": renderOpen }

    empty = True

    for item in showlist:
        if item in render:
            target.comment(repr(item))
            if render[item]():
                empty = False
                yield flush(target)

    if empty:
        document.addExternalStylesheet("resource/message.css")
        body.div("message paleyellow").h1("center").text("No reviews!")

    profiler.output(db=db, user=user, target=document)

    yield flush(None)
