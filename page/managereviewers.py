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
import review.utils as review_utils

def renderManageReviewers(req, db, user):
    review_id = req.getParameter("review", filter=int)

    cursor = db.cursor()

    review = dbutils.Review.fromId(db, review_id)

    root_directories = {}
    root_files = {}

    def processFile(file_id):
        components = dbutils.describe_file(db, file_id).split("/")
        directories, files = root_directories, root_files
        for directory_name in components[:-1]:
            directories, files = directories.setdefault(directory_name, ({}, {}))
        files[components[-1]] = file_id

    cursor.execute("SELECT file FROM reviewfiles WHERE review=%s", (review.id,))

    for (file_id,) in cursor:
        processFile(file_id)

    cursor.execute("SELECT name FROM users WHERE name IS NOT NULL")
    users = [user_name for (user_name,) in cursor if user_name]

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, lambda target: review_utils.renderDraftItems(db, user, review, target), extra_links=[("r/%d" % review.id, "Back to Review", True)])

    document.addExternalStylesheet("resource/managereviewers.css")
    document.addExternalScript("resource/managereviewers.js")
    document.addInternalScript(user.getJS());
    document.addInternalScript(review.getJS());
    document.addInternalScript("var users = [ %s ];" % ", ".join([htmlutils.jsify(user_name) for user_name in sorted(users)]))

    target = body.div("main")

    basic = target.table('manage paleyellow', align='center')
    basic.col(width='10%')
    basic.col(width='60%')
    basic.col(width='30%')
    basic.tr().td('h1', colspan=3).h1().text("Manage Reviewers")

    row = basic.tr("current")
    row.td("select").text("Current:")
    cell = row.td("value")
    for index, reviewer in enumerate(review.reviewers):
        if index != 0: cell.text(", ")
        cell.span("reviewer", critic_username=reviewer.name).innerHTML(htmlutils.htmlify(reviewer.fullname).replace(" ", "&nbsp;"))
    row.td("right").text()

    row = basic.tr("reviewer")
    row.td("select").text("Reviewer:")
    row.td("value").input("reviewer").span("message")
    row.td("right").button("save").text("Save")

    row = basic.tr("help")
    row.td("help", colspan=3).text("Enter the name of a current reviewer to edit assignments (or unassign.)  Enter the name of another user to add a new reviewer.")

    row = basic.tr("headings")
    row.td("select").text("Assigned")
    row.td("path").text("Path")
    row.td().text()

    def outputDirectory(base, name, directories, files):
        if name:
            level = base.count("/")
            row = basic.tr("directory", critic_level=level)
            row.td("select").input(type="checkbox")
            if level > 1:
                row.td("path").preformatted().innerHTML((" " * (len(base) - 2)) + "&#8230;/" + name + "/")
            else:
                row.td("path").preformatted().innerHTML(base + name + "/")
            row.td().text()
        else:
            level = 0

        for directory_name in sorted(directories.keys()):
            outputDirectory(base + name + "/" if name else "", directory_name, directories[directory_name][0], directories[directory_name][1])

        for file_name in sorted(files.keys()):
            row = basic.tr("file", critic_file_id=files[file_name], critic_level=level + 1)
            row.td("select").input(type="checkbox")
            row.td("path").preformatted().innerHTML((" " * (len(base + name) - 1)) + "&#8230;/" + htmlutils.htmlify(file_name))
            row.td().text()

    outputDirectory("", "", root_directories, root_files)

    return document
