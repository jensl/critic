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

import htmlutils
import textutils
import page.utils

def renderSearch(req, db, user):
    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, current_page="search")

    document.addExternalStylesheet("resource/search.css")
    document.addExternalScript("resource/search.js")
    document.addExternalScript("resource/autocomplete.js")
    document.addInternalScript(user.getJS())

    cursor = db.cursor()
    cursor.execute("SELECT name, fullname FROM users")

    users = dict(cursor)

    document.addInternalScript("var users = %s;" % textutils.json_encode(users))

    def renderQuickSearch(target):
        container = target.div("quicksearch-callout")
        container.p().text("""\
A quick search dialog can be opened from all Critic pages using the F keyboard
shortcut.""")
        container.p().a(href="/tutorial?item=search").text("More information")

    def renderSummary(target):
        target.input(name="summary")
    def renderDescription(target):
        target.input(name="description")
    def renderRepository(target):
        page.utils.generateRepositorySelect(
            db, user, target, name="repository", selected=False,
            none_label="Any repository", allow_selecting_none=True)
    def renderBranch(target):
        target.input(name="branch")
    def renderPath(target):
        target.input(name="path")
    def renderUser(target):
        target.input(name="user")
    def renderOwner(target):
        target.input(name="owner")
    def renderReviewer(target):
        target.input(name="reviewer")
    def renderState(target):
        select = target.select(name="state")
        select.option(value="-").text("Any state")
        select.option(value="open").text("Open")
        select.option(value="pending").text("Pending")
        select.option(value="accepted").text("Accepted")
        select.option(value="closed").text("Finished")
        select.option(value="dropped").text("Dropped")

    def renderButton(target):
        target.button(onclick="search();").text("Search")

    search = page.utils.PaleYellowTable(body, "Review Search")
    search.addCentered(renderQuickSearch)
    search.addSeparator()
    search.addItem("Summary", renderSummary)
    search.addItem("Description", renderDescription)
    search.addItem("Repository", renderRepository)
    search.addItem("Branch", renderBranch)
    search.addItem("Path", renderPath)
    search.addItem("User", renderUser)
    search.addItem("Owner", renderOwner)
    search.addItem("Reviewer", renderReviewer)
    search.addItem("State", renderState)
    search.addCentered(renderButton)

    return document
