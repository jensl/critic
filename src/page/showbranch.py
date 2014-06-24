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

import page.utils
import gitutils
import dbutils
import htmlutils
import configuration
import request

import log.html as log_html

def renderShowBranch(req, db, user):
    branch_name = req.getParameter("branch")
    base_name = req.getParameter("base", None)
    review_id = req.getParameter("review", None, filter=int)

    repository = req.getParameter("repository", user.getPreference(db, "defaultRepository"))
    if not repository:
        raise request.MissingParameter("repository")
    repository = gitutils.Repository.fromParameter(db, repository)

    cursor = db.cursor()

    cursor.execute("SELECT id, type, base, head, tail FROM branches WHERE name=%s AND repository=%s", (branch_name, repository.id))

    try:
        branch_id, branch_type, base_id, head_id, tail_id = cursor.fetchone()
    except:
        return page.utils.displayMessage(db, req, user, "'%s' doesn't name a branch!" % branch_name)

    branch = dbutils.Branch.fromName(db, repository, branch_name)
    rebased = False

    if base_name:
        base = dbutils.Branch.fromName(db, repository, base_name)

        if base is None:
            return page.utils.displayMessage(db, req, user, "'%s' doesn't name a branch!" % base_name)

        old_count, new_count, base_old_count, base_new_count = branch.rebase(db, base)

        if base_old_count is not None:
            new_base_base_name = base.base.name
        else:
            new_base_base_name = None

        rebased = True

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    document.addExternalStylesheet("resource/showbranch.css")

    def renderCreateReview(target):
        if not user.isAnonymous() and branch and branch.review is None and not rebased:
            url = htmlutils.URL("/createreview", repository=repository.id, branch=branch_name)
            target.a("button", href=url).text("Create Review")

    if review_id is not None:
        review = dbutils.Review.fromId(db, review_id)
    else:
        review = None

    if review:
        extra_links = [("r/%d" % review.id, "Back to Review")]
        document.addInternalScript(review.getJS())
    else:
        extra_links = []

    page.utils.generateHeader(body, db, user, renderCreateReview, extra_links=extra_links)

    document.addInternalScript(branch.getJS())

    title_right = None

    if rebased:
        def renderPerformRebase(db, target):
            target.button("perform", onclick="rebase(%s, %s, %s, %s, %s, %s, %s)" % tuple(map(htmlutils.jsify, [branch_name, base_name, new_base_base_name, old_count, new_count, base_old_count, base_new_count]))).text("Perform Rebase")

        title_right = renderPerformRebase
    elif base_id is not None:
        bases = []
        base = branch.base

        if base:
            if base.type == "review":
                bases.append("master")
            else:
                base = base.base
                while base:
                    bases.append(base.name)
                    base = base.base

        cursor.execute("SELECT name FROM branches WHERE base=%s", (branch.id,))

        for (name,) in cursor:
            bases.append(name)

        def renderSelectBase(db, target):
            select = target.select("base")
            select.option(value="*").text("Select new base")
            select.option(value="*").text("---------------")

            for name in bases:
                select.option("base", value=name.split(" ")[0]).text(name)

        if not bases and branch.base:
            cursor.execute("SELECT commit FROM reachable WHERE branch=%s", (branch.id,))

            commit_ids = cursor.fetchall()

            body.comment(repr(commit_ids))

            for commit_id in commit_ids:
                cursor.execute("SELECT 1 FROM reachable WHERE branch=%s AND commit=%s", (branch.base.id, commit_id))
                if cursor.fetchone():
                    bases.append("%s (trim)" % branch.base.name)
                    break

        if bases:
            title_right = renderSelectBase

    target = body.div("main")

    if branch_type == 'normal':
        cursor.execute("SELECT COUNT(*) FROM reachable WHERE branch=%s", (branch_id,))

        commit_count = cursor.fetchone()[0]
        if commit_count > configuration.limits.MAXIMUM_REACHABLE_COMMITS:
            offset = req.getParameter("offset", default=0, filter=int)
            limit = req.getParameter("limit", default=200, filter=int)

            head = gitutils.Commit.fromId(db, repository, head_id)
            tail = gitutils.Commit.fromId(db, repository, tail_id) if tail_id else None

            sha1s = repository.revlist([head], [tail] if tail else [], "--skip=%d" % offset, "--max-count=%d" % limit)
            commits = [gitutils.Commit.fromSHA1(db, repository, sha1) for sha1 in sha1s]

            def moreCommits(db, target):
                target.a(href="/log?branch=%s&offset=%d&limit=%d" % (branch_name, offset + limit, limit)).text("More commits...")

            log_html.renderList(db, target, branch.name, commits, title_right=title_right, bottom_right=moreCommits)

            return document

    branch.loadCommits(db)

    log_html.render(db, target, branch.name, branch=branch, title_right=title_right)

    return document
