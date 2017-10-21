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

import urllib.parse

import htmlutils
import textutils
import page.utils

def renderSearch(req, db, user):
    document = htmlutils.Document(req)
    document.setTitle("Review Search")

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
        wrap = target.div("quicksearch callout")
        wrap.p().text("""A Quick Search dialog can be opened from any page
                         using the "F" keyboard shortcut.""")
        wrap.p().a(href="/tutorial?item=search").text("More information")

    def renderInput(target, label, name, placeholder=""):
        fieldset = target.fieldset("search-" + name)
        fieldset.label("input-label").text(label)
        fieldset.input(type="text", name=name, placeholder=placeholder)

    def renderInputWithOptions(target, label, name, options, placeholder=""):
        fieldset = target.fieldset("search-" + name)
        fieldset.label("input-label").text(label)
        checkGroup = fieldset.div("input-options checkbox-group")
        for option in options:
            opt_label = checkGroup.label()
            opt_label.input(type="checkbox", name=option["name"],
                            checked="checked" if "checked" in option else None)
            opt_label.text(option["label"])
        fieldset.input(type="text", name=name, placeholder=placeholder)

    def renderFreetext(target):
        options=[{ "name": "freetextSummary", "label": "Summary",
                   "checked": True },
                 { "name": "freetextDescription", "label": "Description",
                   "checked": True }]
        renderInputWithOptions(target, label="Search term", name="freetext",
                               placeholder="free text search", options=options)

    def renderState(target):
        state = target.fieldset("search-state")
        state.label("input-label").text("State")
        select = state.select(name="state")
        select.option(value="", selected="selected").text("Any state")
        select.option(value="open").text("Open")
        select.option(value="pending").text("Pending")
        select.option(value="accepted").text("Accepted")
        select.option(value="closed").text("Finished")
        select.option(value="dropped").text("Dropped")

    def renderUser(target):
        options=[{ "name": "userOwner", "label": "Owner", "checked": True },
                 { "name": "userReviewer", "label": "Reviewer" }]
        renderInputWithOptions(target, label="User", name="user",
                               placeholder="user name(s)", options=options)

    def renderRepository(target):
        fieldset = target.fieldset("search-repository")
        fieldset.label("input-label").text("Repository")
        page.utils.generateRepositorySelect(
            db, user, fieldset, name="repository", selected=False,
            placeholder_text="Any repository", allow_selecting_none=True)

    section = body.section("paleyellow section")
    section.h1("section-heading").text("Review Search")

    url_terms = []

    for name, value in urllib.parse.parse_qsl(req.query):
        if name == "q":
            url_terms.append(value)
        elif name.startswith("q"):
            url_terms.append("%s:%s" % (name[1:], value))

    wrap = section.div("flex")
    search = wrap.form("search", name="search")

    if url_terms:
        row = search.div("flex")
        query = row.fieldset("search-query")
        query.label("input-label").text("Search query")
        query.input(type="text", name="query", value=" ".join(url_terms))

        result = section.div("search-result", style="display: none")
        result.h2().text("Search result")
        result.div("callout")
    else:
        row = search.div("flex")
        renderFreetext(row)
        renderState(row)

        renderUser(search)

        row = search.div("flex")
        renderRepository(row)
        renderInput(row, "Branch", "branch")

        renderInput(search, "Path", "path")

    buttons = search.div("search-buttons")

    if url_terms:
        buttons.button(type="submit").text("Search again")
        buttons.a("button", href="/search").text("Show full search form")
    else:
        buttons.button(type="submit").text("Search")

    renderQuickSearch(wrap)

    return document
