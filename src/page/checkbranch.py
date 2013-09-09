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
import htmlutils
import page.utils
import gitutils
import dbutils
import re
import log.commitset

def addNote(req, db, user):
    repository_id = req.getParameter("repository", filter=int)
    branch = req.getParameter("branch")
    upstream = req.getParameter("upstream")
    sha1 = req.getParameter("sha1")
    review_id = req.getParameter("review", None)
    text = req.read().strip()

    if review_id is not None:
        review = dbutils.Review.fromId(db, review_id)
    else:
        review = None

    cursor = db.cursor()
    cursor.execute("DELETE FROM checkbranchnotes WHERE repository=%s AND branch=%s AND upstream=%s AND sha1=%s",
                   (repository_id, branch, upstream, sha1))
    cursor.execute("INSERT INTO checkbranchnotes (repository, branch, upstream, sha1, uid, review, text) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                   (repository_id, branch, upstream, sha1, user.id, review_id, text or None))
    db.commit()

    response = "ok"

    if review and review.repository.id == repository_id:
        repository = gitutils.Repository.fromId(db, repository_id)
        commit = gitutils.Commit.fromSHA1(db, repository, sha1)
        commitset = log.commitset.CommitSet(review.branch.commits)

        upstreams = commitset.getFilteredTails(repository)
        if len(upstreams) == 1:
            upstream = upstreams.pop()
            if repository.mergebase([commit.sha1, upstream]) == upstream:
                response = "rebase"

    return response

def deleteNote(req, db, user):
    repository_id = req.getParameter("repository", filter=int)
    branch = req.getParameter("branch")
    upstream = req.getParameter("upstream")
    sha1 = req.getParameter("sha1")

    cursor = db.cursor()
    cursor.execute("DELETE FROM checkbranchnotes WHERE repository=%s AND branch=%s AND upstream=%s AND sha1=%s",
                   (repository_id, branch, upstream, sha1))
    db.commit()

    return "ok"

def renderCheckBranch(req, db, user):
    mode = "html" if req.path == "checkbranch" else "text"

    repository_arg = req.getParameter("repository", None)

    cursor = db.cursor()
    header_right = []

    if mode == "html":
        document = htmlutils.Document(req)

        html = document.html()
        head = html.head()
        body = html.body()

        def generateRight(target):
            header_right.append(target.div("buttons"))

        page.utils.generateHeader(body, db, user, generate_right=generateRight)

        document.addExternalStylesheet("resource/checkbranch.css")
        document.addExternalScript("resource/checkbranch.js")
        document.addInternalScript(user.getJS())

        target = body.div("main")
    else:
        result = ""

    if repository_arg is not None:
        repository = gitutils.Repository.fromParameter(db, repository_arg)
        branch_arg = commit = req.getParameter("commit")
        fetch = req.getParameter("fetch", "no") == "yes"
        upstream_arg = req.getParameter("upstream", "master")

        if mode == "html":
            header_right[0].a("button", href="tutorial?item=checkbranch").text("Help")
            header_right[0].a("button", href="checkbranchtext?repository=%s&commit=%s&upstream=%s" % (repository_arg, branch_arg, upstream_arg)).text("Get Textual Log")
            header_right[0].span("buttonscope buttonscope-global")
            target.addInternalScript(repository.getJS());
            target.addInternalScript("var branch = %r, upstream = %r;" % (branch_arg, upstream_arg))

        upstream = repository.revparse(upstream_arg)

        if fetch:
            if commit.startswith("r/"):
                raise page.utils.DisplayMessage, "Won't fetch review branch from remote!"
            repository.updateBranchFromRemote(db, repository.getDefaultRemote(db), commit)

        try: commit = repository.revparse(commit)
        except: raise page.utils.DisplayMessage, "Unable to interpret '%s' as a commit reference." % commit

        try: gitutils.Commit.fromSHA1(db, repository, commit)
        except: raise page.utils.DisplayMessage, "'%s' doesn't exist in the repository." % commit

        if mode == "html":
            document.setTitle("Branch review status: %s" % branch_arg)

        commits = repository.revlist([commit], [upstream], "--topo-order")

        if not commits:
            try: merge_sha1 = repository.revlist([upstream], [commit], "--topo-order", "--ancestry-path")[-1]
            except: raise page.utils.DisplayMessage, "No merged or unmerged commits found."

            merge = gitutils.Commit.fromSHA1(db, repository, merge_sha1)

            if len(merge.parents) == 1:
                candidate_merges = repository.revlist([commit], [], "--topo-order", "--max-count=256")
                for merge_sha1 in candidate_merges:
                    merge = gitutils.Commit.fromSHA1(db, repository, merge_sha1)
                    if len(merge.parents) > 1:
                        use_upstream = merge.parents[1]
                        break
                else:
                    raise page.utils.DisplayMessage, "Merge into upstream was a fast-forward; can't figure out what was merged in."
            else:
                assert commit in merge.parents

                use_upstream = None
                for parent in merge.parents:
                    if parent != commit:
                        use_upstream = parent
                        break

            commits = repository.revlist([commit], [use_upstream], "--topo-order")
            title = "Merged Commits (%d)" % len(commits)
            display_upstream = gitutils.Commit.fromSHA1(db, repository, use_upstream).describe(db)
        else:
            title = "Unmerged Commits (%d)" % len(commits)
            display_upstream = upstream_arg

        commits = [gitutils.Commit.fromSHA1(db, repository, sha1) for sha1 in commits]

        if mode == "html":
            table = target.table("branchstatus paleyellow", align="center", cellspacing=0)
            table.col(width="10%")
            table.col(width="8%")
            table.col(width="77%")
            table.col(width="5%")

            thead = table.thead()
            h1_cell = thead.tr().td('h1', colspan=4)
            h1_cell.h1().text(title)
            p = h1_cell.p()
            p.text("Commits returned by the command: ")
            p.span("command").text("git rev-list --topo-order %s ^%s" % (branch_arg, display_upstream))

            row = thead.tr("headings")
            row.th("sha1").text("SHA-1")
            row.th("user").text("Committer")
            row.th("summary").text("Summary")
            row.th("Review").text("Review")

        cursor.execute("""SELECT sha1, uid, review, text
                            FROM checkbranchnotes
                           WHERE repository=%s
                             AND branch=%s
                             AND upstream=%s""",
                       (repository.id, branch_arg, upstream_arg))

        notes = {}
        reds = False

        for sha1, user_id, review_id, text in cursor:
            notes[sha1] = dbutils.User.fromId(db, user_id), review_id, text

        if commits:
            merged = set(commits)
            handled = set()

            current_tbody = None
            last_tbody = None

            def nameFromEmail(email):
                offset = email.find("@")
                if offset != -1: return email[:offset]
                else: return email

            review = None
            reviewed_commits = []

            text_items = {}
            text_order = []

            for commit in commits:
                if commit not in handled:
                    cursor.execute("""SELECT reviews.id
                                        FROM reviews
                                        JOIN branches ON (branches.id=reviews.branch)
                                        JOIN commits ON (commits.id=branches.head)
                                       WHERE commits.sha1=%s AND reviews.state!='dropped'""",
                                   (commit.sha1,))

                    if commit not in reviewed_commits:
                        review = None

                    reviewed = set()
                    best = 0

                    for (review_id,) in cursor:
                        candidate_review = dbutils.Review.fromId(db, review_id)
                        candidate_reviewed = filter(lambda commit: commit in merged, candidate_review.branch.commits)

                        if len(candidate_reviewed) > best:
                            review = candidate_review
                            reviewed = candidate_reviewed
                            best = len(reviewed)

                        reviewed_commits = filter(lambda commit: commit in reviewed, commits)

                    if mode == "html":
                        if review:
                            current_tbody = None

                            review_tbody = table.tbody("reviewed" if review.state == 'closed' or review.accepted(db) else "pending")
                            first = True

                            review_tbody.tr("empty").td("empty", colspan=4)

                            for reviewed_commit in reviewed_commits:
                                handled.add(reviewed_commit)

                                row = review_tbody.tr("commit")
                                row.td("sha1", title=commit.sha1).div().text(reviewed_commit.sha1[:8])
                                row.td("user").text(nameFromEmail(reviewed_commit.committer.email))
                                row.td("summary").a(href="%s?review=%d" % (reviewed_commit.sha1, review.id)).text(reviewed_commit.niceSummary())

                                if first:
                                    row.td("review", rowspan=len(reviewed)).a(href="r/%d" % review.id).text("r/%d" % review.id)
                                    first = False

                            last_tbody = review_tbody
                        elif commit.sha1 in notes:
                            note_user, review_id, text = notes[commit.sha1]

                            try: review = dbutils.Review.fromId(db, review_id) if review_id else None
                            except: review = None

                            current_tbody = None

                            note_tbody = table.tbody("note" if (not review_id or (review and (review.state == 'closed' or review.accepted(db)))) else "pending")
                            note_tbody.tr("empty").td("empty", colspan=4)

                            row = note_tbody.tr("commit", id=commit.sha1)
                            row.td("sha1", title=commit.sha1).div().text(commit.sha1[:8])
                            row.td("user").text(nameFromEmail(commit.committer.email))
                            row.td("summary").a(href="%s?repository=%d" % (commit.sha1, repository.id)).text(commit.niceSummary())

                            cell = row.td("review")

                            if review_id is None: cell.text()
                            else: cell.a(href="r/%d" % review_id).text("r/%d" % review_id)

                            row = note_tbody.tr("note")
                            row.td("sha1").text()

                            cell = row.td("note", colspan=2)
                            cell.text("Set by ")
                            cell.span("user").text(note_user.fullname)
                            if text is not None:
                                cell.text(": ")
                                cell.span("text").text(text)

                            row.td("edit").a("edit", href="javascript:editCommit(%r, %d, true%s);" % (commit.sha1, commit.getId(db), (", %d" % review_id) if review_id is not None else "")).text("[edit]")

                            last_tbody = note_tbody
                        else:
                            handled.add(commit)

                            if not current_tbody:
                                current_tbody = table.tbody("unknown")
                                current_tbody.tr("empty").td("empty", colspan=4)
                                last_tbody = current_tbody

                            row = current_tbody.tr("commit%s" % (" own" if commit.author.email == user.email else ""), id=commit.sha1)
                            row.td("sha1", title=commit.sha1).div().text(commit.sha1[:8])
                            row.td("user").text(nameFromEmail(commit.committer.email))
                            row.td("summary").a(href="%s/%s" % (repository.name, commit.sha1)).text(commit.niceSummary())
                            row.td("edit").a("edit", href="javascript:editCommit(%r, %d, false);" % (commit.sha1, commit.getId(db))).text("[edit]")

                            reds = True
                    else:
                        match = re.search("[A-Z][A-Z0-9]*-[0-9]+", commit.summary())

                        if match:
                            title = match.group(0)
                        else:
                            title = commit.summary(maxlen=50)
                            if title.endswith(".") and not title.endswith("..."):
                                title = title[:-1]

                        if commit.sha1 in notes:
                            note_user, review_id, text = notes[commit.sha1]
                            if review_id: review = dbutils.Review.fromId(db, review_id)
                        else:
                            text = None

                        if review:
                            item = review.getURL(db)
                            if review.state != "closed" and not review.accepted(db):
                                item += " (NOT ACCEPTED!)"
                            if text:
                                item += " (%s: %s)" % (note_user.fullname, text)
                        elif text:
                            item = "%s: %s" % (note_user.fullname, text)
                        else:
                            item = "REVIEW STATUS UNKNOWN!"

                        if title in text_items:
                            if item not in text_items[title]:
                                text_items[title].append(item)
                        else:
                            text_items[title] = [item]
                            text_order.append(title)

            if mode == "html":
                last_tbody.tr("empty").td("empty", colspan=4)
            else:
                for title in reversed(text_order):
                    result += "%s: %s\n" % (title, ", ".join(text_items[title]))

        if mode == "html":
            if reds:
                h1_cell.h2().text("There should be no red!")

            legend = target.div("legend")
            legend.text("Color legend: ")
            legend.span("red").text("Status unknown")
            legend.text(" ")
            legend.span("yellow").text("Status set manually")
            legend.text(" ")
            legend.span("green").text("Verified by Critic")

            return document
        else:
            return result
    else:
        header_right[0].a("button", href="tutorial?item=checkbranch").text("Help")

        table = page.utils.PaleYellowTable(target, "Check branch review status")

        def renderRepository(target):
            page.utils.generateRepositorySelect(db, user, target, name="repository")
        def renderBranchName(target):
            target.input(name="commit")
        def renderFetch(target):
            target.input(name="fetch", type="checkbox", value="yes")
        def renderUpstream(target):
            target.input(name="upstream", value="master")

        table.addItem("Repository", renderRepository, description="Repository.")
        table.addItem("Branch name", renderBranchName,
                      description="Branch name, or other reference to a commit.")
        table.addItem("Fetch branch from remote", renderFetch,
                      description=("Fetch named branch from selected repository's "
                                   "primary remote (from whence its 'master' branch "
                                   "is auto-updated.)"))
        table.addItem("Upstream", renderUpstream,
                      description="Name of upstream branch.")

        def renderCheck(target):
            target.button("check").text("Check branch")

        table.addCentered(renderCheck)

        return document
