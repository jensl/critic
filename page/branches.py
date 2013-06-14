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
import configuration

def linkToBranch(target, repository, name):
    target.a(href="log?branch=%s&repository=%d" % (name, repository.id)).text(name)

class ExtraColumn:
    def __init__(self, className, heading, render):
        self.className = className
        self.heading = heading
        self.render = render

def render(db, user, target, title, repository, branches, linkToBranch=linkToBranch, extraColumns=[], description=""):
    target.addExternalStylesheet("resource/branches.css")

    cursor = db.cursor()

    table = target.table("paleyellow branches", align="center", cellspacing="0")

    row = table.tr("title")
    row.td("h1", colspan=1 + len(extraColumns)).h1().text(title)
    repositories = row.td("repositories", colspan="2").select()

    if not repository:
        repositories.option(value="-", selected="selected", disabled="disabled").text("Select a repository")

    cursor.execute("SELECT id, path FROM repositories ORDER BY id")
    for id, path in cursor:
        repositories.option(value=id, selected="selected" if repository and id == repository.id else None).text(gitutils.Repository.constructURL(db, user, path))

    if branches:
        values = []

        if isinstance(branches[0], int) or isinstance(branches[0], long):
            for branch_id in branches:
                cursor.execute("SELECT branches.name, branches.review, bases.name, count(reachable.branch) FROM branches LEFT OUTER JOIN branches AS bases ON (branches.base=bases.id) LEFT OUTER JOIN reachable ON (branches.id=reachable.branch) WHERE branches.id=%s GROUP BY branches.name, branches.review, bases.name", [branch_id])
                values.append(cursor.fetchone())
        else:
            for branch_name in branches:
                cursor.execute("SELECT branches.name, branches.review, bases.name, count(reachable.branch) FROM branches LEFT OUTER JOIN branches AS bases ON (branches.base=bases.id), reachable WHERE branches.name=%s AND branches.id=reachable.branch GROUP BY branches.name, branches.review, bases.name", [branch_name])
                values.append(cursor.fetchone())

        row = table.tr("headings")
        row.td("name").text("Name")
        row.td("base").text("Base")
        row.td("commits").text("Commits")

        for extraColumn in extraColumns:
            row.td(extraColumn.className).text(extraColumn.heading)

        for index, (name, review_id, base, count) in enumerate(values):
            row = table.tr("branch")
            cell = row.td("name")
            linkToBranch(cell, repository, name)

            if review_id is not None:
                span = cell.span("review").preformatted()
                span.a(href="r/%d" % review_id).text("r/%d" % review_id)
            elif base:
                span = cell.span("check").preformatted()
                span.a(href="checkbranch?repository=%d&commit=%s&upstream=%s&fetch=no" % (repository.id, name, base)).text("check")

            if base: linkToBranch(row.td("base"), repository, base)
            else: row.td("base")
            row.td("commits").text(count)

            for extraColumn in extraColumns:
                extraColumn.render(row.td(extraColumn.className), index)
    else:
        row = table.tr("nothing")
        row.td("nothing", colspan=3).text("No branches" if repository else "No repository selected")

def renderBranches(req, db, user):
    offset = req.getParameter("offset", 0, filter=int)
    count = req.getParameter("count", 50, filter=int)

    cursor = db.cursor()

    repository = req.getParameter("repository", None, gitutils.Repository.FromParameter(db))

    if not repository:
        repository = user.getDefaultRepository(db)

    all_branches = []
    commit_times = []

    if repository:
        cursor.execute("""SELECT branches.id, branches.name, commits.commit_time
                            FROM branches
                            JOIN repositories ON (repositories.id=branches.repository)
                            JOIN commits ON (commits.id=branches.head)
                           WHERE branches.type='normal'
                             AND branches.name NOT LIKE 'replay/%%'
                             AND repositories.id=%s
                        ORDER BY commits.commit_time DESC LIMIT %s""",
                       (repository.id, count))

        for branch_id, branch_name, commit_time in cursor.fetchall():
            all_branches.append(branch_id)
            commit_times.append(commit_time.timetuple())

    document = htmlutils.Document(req)

    if repository:
        document.setTitle("Branches in %s" % repository.name)
    else:
        document.setTitle("Branches")

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, current_page="branches")

    document.addExternalScript("resource/branches.js")

    if repository:
        document.addInternalScript(repository.getJS())

    extraColumns = [ExtraColumn("when", "When", lambda target, index: log.html.renderWhen(target, commit_times[index]))]

    render(db, user, body.div("main"), "All Branches", repository, all_branches[offset:], extraColumns=extraColumns)

    return document
