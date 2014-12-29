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

import itertools

import dbutils
import gitutils
import log.html
import htmlutils
import page.utils

def renderBranches(req, db, user):
    offset = req.getParameter("offset", 0, filter=int)
    count = req.getParameter("count", 50, filter=int)

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, current_page="branches")

    document.addExternalScript("resource/branches.js")
    document.addExternalStylesheet("resource/branches.css")

    cursor = db.cursor()

    repository = req.getParameter("repository", None, gitutils.Repository.FromParameter(db))

    if not repository:
        repository = user.getDefaultRepository(db)

    if repository:
        title = "Branches in %s" % repository.name
        selected = repository.name
    else:
        title = "Branches"
        selected = None

    document.setTitle(title)

    table = body.div("main").table("paleyellow branches", align="center", cellspacing="0")

    row = table.tr("title")
    row.td("h1", colspan=2).h1().text(title)

    page.utils.generateRepositorySelect(db, user, row.td("repositories", colspan=2), selected=selected)

    if repository:
        document.addInternalScript(repository.getJS())

        cursor.execute("""SELECT branches.id, branches.name, branches.base, branches.review,
                                 branches.commit_time, COUNT(reachable.branch)
                            FROM (SELECT branches.id AS id, branches.name AS name, bases.name AS base,
                                         reviews.id AS review, commits.commit_time AS commit_time
                                    FROM branches
                                    JOIN commits ON (commits.id=branches.head)
                         LEFT OUTER JOIN reviews ON (reviews.origin=branches.id)
                         LEFT OUTER JOIN branches AS bases ON (branches.base=bases.id)
                                   WHERE branches.type='normal'
                                     AND branches.repository=%s
                                ORDER BY commits.commit_time DESC
                                   LIMIT %s
                                   OFFSET %s) AS branches
                 LEFT OUTER JOIN reachable ON (reachable.branch=branches.id)
                        GROUP BY branches.id, branches.name, branches.base, branches.review,
                                 branches.commit_time
                        ORDER BY branches.commit_time DESC""",
                       (repository.id, count, offset))

        branches_found = False

        for branch_id, branch_name, base_name, review_id, commit_time, count in cursor:
            if not branches_found:
                row = table.tr("headings")
                row.td("name").text("Name")
                row.td("base").text("Base")
                row.td("commits").text("Commits")
                row.td("when").text("When")
                branches_found = True

            row = table.tr("branch")

            def link_to_branch(target, repository, name):
                url = htmlutils.URL("/log", branch=name, repository=repository.id)
                target.a(href=url).text(name)

            td_name = row.td("name")
            link_to_branch(td_name, repository, branch_name)

            if review_id is not None:
                span = td_name.span("review").preformatted()
                span.a(href="r/%d" % review_id).text("r/%d" % review_id)
            elif base_name:
                url = htmlutils.URL("/checkbranch",
                                    repository=repository.id,
                                    commit=branch_name,
                                    upstream=base_name,
                                    fetch="no")
                span = td_name.span("check").preformatted().a(href=url).text("check")

            td_base = row.td("base")
            if base_name:
                link_to_branch(td_base, repository, base_name)

            row.td("commits").text(count)

            log.html.renderWhen(row.td("when"), commit_time.timetuple())

        if not branches_found:
            row = table.tr("nothing")
            row.td("nothing", colspan=4).text("No branches")
    else:
        row = table.tr("nothing")
        row.td("nothing", colspan=4).text("No repository selected")

    return document
