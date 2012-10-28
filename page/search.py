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

def renderSearch(req, db, user):
    summary_value = req.getParameter("summary", None)
    summary_mode_value = req.getParameter("summarymode", None)
    branch_value = req.getParameter("branch", None)
    owner_value = req.getParameter("owner", None)
    path_value = req.getParameter("path", None)

    document = htmlutils.Document(req)
    document.setTitle("Search")

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, current_page="search")

    document.addExternalStylesheet("resource/search.css")
    document.addExternalScript("resource/search.js")
    document.addInternalScript(user.getJS())

    cursor = db.cursor()
    cursor.execute("SELECT DISTINCT name, fullname FROM users JOIN reviewusers ON (reviewusers.uid=users.id) WHERE reviewusers.owner")

    users = [("{ label: %s, value: %s }" % (htmlutils.jsify("%s (%s)" % (fullname, name)),
                                            htmlutils.jsify(name)))
             for name, fullname in cursor]

    document.addInternalScript("var users = [ %s ];" % ", ".join(users))

    search = page.utils.PaleYellowTable(body, "Search")

    def renderSummary(target):
        target.input(name="summary", value=summary_value or "")
        summary_mode = target.select(name="summary_mode")
        summary_mode.option(value="all", selected="selected" if summary_mode_value == "all" else None).text("All words")
        summary_mode.option(value="any", selected="selected" if summary_mode_value == "any" else None).text("Any word")

    def renderBranch(target):
        target.input(name="branch", value=branch_value or "")

    def renderOwner(target):
        target.input(name="owner", value=owner_value or "")

    def renderPath(target):
        target.input(name="path", value=path_value or "")

    def renderButton(target):
        target.button(onclick="search();").text("Search")

    search.addItem("Summary", renderSummary, "Words occuring in the review's summary.")
    search.addItem("Branch", renderBranch, "Name of review branch.")
    search.addItem("Owner", renderOwner, "Owner of the review.")
    search.addItem("Path", renderPath, "Path (file or directory) that the review contains changes in.")
    search.addCentered(renderButton)

    if summary_value is not None: summary_value = summary_value.strip()
    if branch_value is not None: branch_value = branch_value.strip()
    if owner_value is not None: owner_value = owner_value.strip()
    if path_value is not None: path_value = path_value.strip()

    if summary_value or branch_value or owner_value or path_value:
        query = """SELECT DISTINCT reviews.id, reviews.summary, branches.name
                     FROM %s
                    WHERE %s"""

        tables = ["reviews", "branches ON (branches.id=reviews.branch)"]
        conditions = []
        arguments = []

        if summary_value:
            words = summary_value.split()
            operator = " AND " if summary_mode_value == "all" else " OR "
            conditions.append("(%s)" % operator.join(["reviews.summary ~* %s"] * len(words)))
            arguments.extend([".*\\m" + word + "\\M.*" for word in words])

        if branch_value:
            def globToSQLPattern(glob):
                pattern = glob.replace("\\", "\\\\").replace("%", "\\%").replace("?", "_").replace("*", "%")
                if pattern[0] != "%": pattern = "%" + pattern
                if pattern[-1] != "%": pattern = pattern + "%"
                return pattern

            conditions.append("branches.name LIKE %s")
            arguments.append(globToSQLPattern(branch_value))

        if owner_value:
            owner = dbutils.User.fromName(db, owner_value)
            tables.append("reviewusers ON (reviewusers.review=reviews.id)")
            conditions.append("reviewusers.uid=%s")
            conditions.append("reviewusers.owner")
            arguments.append(owner.id)

        if path_value:
            file_ids = dbutils.contained_files(db, dbutils.find_directory(db, path_value))

            if path_value[-1] != '/':
                file_ids.append(dbutils.find_file(db, path_value))

            tables.append("reviewfiles ON (reviewfiles.review=reviews.id)")
            conditions.append("reviewfiles.file=ANY (%s)")
            arguments.append(file_ids)

        query = """SELECT DISTINCT reviews.id, reviews.summary, branches.name
                     FROM %s
                    WHERE %s
                 ORDER BY reviews.id""" % (" JOIN ".join(tables), " AND ".join(conditions))

        cursor.execute(query, arguments)

        table = body.div("main").table("paleyellow reviews", align="center")
        table.col(width="20%")
        table.col(width="80%")
        header = table.tr().td("h1", colspan=4).h1()
        header.text("Reviews")

        for review_id, summary, branch_name in cursor:
            row = table.tr("review")
            row.td("name").text(branch_name)
            row.td("title").a(href="r/%d" % review_id).text(summary)

    return document
