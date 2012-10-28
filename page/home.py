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
import configuration

def renderHome(req, db, user):
    cursor = db.cursor()

    readonly = req.getParameter("readonly", "yes" if user.name != req.user else "no") == "yes"
    repository = req.getParameter("repository", None, gitutils.Repository.FromParameter(db))

    if not repository:
        repository = user.getDefaultRepository(db)

    title_fullname = user.fullname

    if title_fullname[-1] == 's': title_fullname += "'"
    else: title_fullname += "'s"

    cursor.execute("SELECT email FROM usergitemails WHERE uid=%s ORDER BY email ASC", (user.id,))
    gitemails = ", ".join([email for (email,) in cursor])

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, current_page="home")

    document.addExternalStylesheet("resource/home.css")
    document.addExternalScript("resource/home.js")
    if repository: document.addInternalScript(repository.getJS())
    else: document.addInternalScript("var repository = null;")
    document.addInternalScript(user.getJS())
    document.addInternalScript("user.gitEmails = %s;" % htmlutils.jsify(gitemails))
    document.setTitle("%s Home" % title_fullname)

    target = body.div("main")

    basic = target.table('paleyellow basic', align='center')
    basic.tr().td('h1', colspan=3).h1().text("%s Home" % title_fullname)

    def row(heading, value, help, status_id=None):
        main_row = basic.tr('line')
        main_row.td('heading').text("%s:" % heading)
        if callable(value): value(main_row.td('value'))
        else: main_row.td('value').text(value)
        main_row.td('status', id=status_id)
        if help: basic.tr('help').td('help', colspan=3).text(help)

    def renderFullname(target):
        if readonly: target.text(user.fullname)
        else:
            target.input("value", id="user_fullname", value=user.fullname)
            target.button(onclick="saveFullname();").text("Save")
            target.button(onclick="resetFullname();").text("Reset")

    def renderEmail(target):
        if readonly: target.text(user.email)
        else:
            target.input("value", id="user_email", value=user.email)
            target.button(onclick="saveEmail();").text("Save")
            target.button(onclick="resetEmail();").text("Reset")

    def renderGitEmails(target):
        if readonly: target.text(gitemails)
        else:
            target.input("value", id="user_gitemails", value=gitemails)
            target.button(onclick="saveGitEmails();").text("Save")
            target.button(onclick="resetGitEmails();").text("Reset")

    row("User ID", str(user.id), "This is the user ID in the database.  It really doesn't matter.")
    row("User Name", user.name, "This is the user name.  You probably already knew that.")
    row("Display Name", renderFullname, "This is the name used when displaying commits or comments.", status_id="status_fullname")
    row("Email", renderEmail, "This is the primary email address, to which emails are sent.", status_id="status_email")
    row("Git Emails", renderGitEmails, "These email addresses are used to map Git commits to the user.", status_id="status_gitemails")

    filters = target.table('paleyellow filters', align='center')
    row = filters.tr()
    row.td("h1", colspan=2).h1().text("Filters")
    repositories = row.td("repositories", colspan=2).select()

    if not repository:
        repositories.option(value="-", selected="selected", disabled="disabled").text("Select a repository")

    cursor.execute("SELECT id, path FROM repositories ORDER BY id")
    for id, path in cursor:
        repositories.option(value=id, selected="selected" if repository and id == repository.id else None).text("%s:%s" % (configuration.base.HOSTNAME, path))

    help = filters.tr().td("help", colspan=4)

    help.p().text("Filters is the system's mechanism to connect reviews to users.  When a review is created or updated, a set of users to associate with the review is calculated by matching the files modified by each commit in the review to the filters set up by users.  Each filter selects one file or one directory (and affects all sub-directories and files,) and only the most specific filter per file and user is used when associating users with reviews.")

    p = help.p()
    p.text("There are two types of filters: ")
    p.code().text("reviewer")
    p.text(" and ")
    p.code().text("watcher")
    p.text(".  All files matched by a ")
    p.code().text("reviewer")
    p.text(" filter for a user are added to the user's to-do list, meaning the user needs to review all changes made to that file before the review is finished.  However, if more than one user is matched as a reviewer for a file, only one of them needs to review the changes.  A user associated with a review only by ")
    p.code().text("watcher")
    p.text(" filters will simply receive notifications relating to the review, but isn't required to do anything.")

    p = help.p()
    p.text("For a ")
    p.code().text("reviewer")
    p.text(" type filter, a set of \"delegates\" can also be defined.  The delegate field should be a comma-separated list of user names.  Delegates are automatically made reviewers of changes by you in the filtered files (since you can't review them yourself) regardless of their own filters.")

    p = help.p()
    p.strong().text("Note: A filter names a directory only if the path ends with a slash ('/').")
    p.text("  If the path doesn't end with a slash, the filter would name a specific file even if the path is a directory in some or all versions of the actual tree.  However, you'll get a warning if you try to add a filter for a file whose path is registered as a directory in the database.")

    if repository:
        headings = filters.tr("headings")
        headings.td("heading type").text("Type")
        headings.td("heading path").text("Path")
        headings.td("heading delegate").text("Delegate")
        headings.td("heading buttons")

        cursor.execute("SELECT directory, file, type, delegate FROM filters WHERE uid=%s AND repository=%s", [user.id, repository.id])

        all_filters = []

        for directory_id, file_id, filter_type, delegate in cursor.fetchall():
            if file_id == 0: path = dbutils.describe_directory(db, directory_id) + "/"
            else: path = dbutils.describe_file(db, file_id)
            all_filters.append((path, directory_id, file_id, filter_type, delegate))

        all_filters.sort()

        empty = filters.tr("empty").td("empty", colspan=4).span(id="empty").text("No filters configured")
        if filters: empty.setAttribute("style", "display: none")

        for path, directory_id, file_id, filter_type, delegate in all_filters:
            row = filters.tr("filter")
            row.td("filter type").text(filter_type.capitalize())
            row.td("filter path").text(path)
            row.td("filter delegate").text(delegate)

            buttons = row.td("filter buttons")
            if readonly: buttons.text()
            else:
                buttons.button(onclick="editFilter(this, %d, %d, false);" % (directory_id, file_id)).text("Edit")
                buttons.button(onclick="deleteFilter(this, %d, %d);" % (directory_id, file_id)).text("Delete")

        if not readonly:
            filters.tr("buttons").td("buttons", colspan=4).button(onclick="addFilter(this);").text("Add Filter")

    return document
