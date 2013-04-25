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
import dbutils
import htmlutils
import configuration
import re
import textformatting

def renderFromFile(db, target, name):
    lines = open("%s/tutorials/%s.txt" % (configuration.paths.INSTALL_DIR, name)).read().splitlines()

    table = target.table("paleyellow", align="center")
    textformatting.renderFormatted(db, table, lines, toc=True)
    table.tr("back").td("back").div().a(href="tutorial").text("Back")

def renderSections(db, user, target):
    table = target.table("paleyellow", align="center")
    table.tr("h1").td("h1").h1().text("Tutorials")

    def section(name, title, description):
        table.tr("h2").td("h2").div().h2().text(title)
        table.tr("text").td("text").div().text(description, cdata=True)
        table.tr("goto").td("goto").div().a(href="tutorial?item=%s" % name).text("Learn More")

    section("request", "Requesting a Review", """\
Introduction to the different ways of requesting a review of changes in
Critic.  You'll be able to request a review of your bug fix in 10 seconds,
using your favorite git client!  (Though it'll take you more than 10
seconds to read all the text&#8230;)""")

    section("review", "Reviewing Changes", """\
Introduction to the process of reviewing changes in Critic.  Covers the
basic concepts, marking changes as reviewed and raising issues, and some
other things.  Useful information both for reviewers and for those
requesting the reviews.""")

    section("filters", "Filters", """\
Information about the Filters mechanism.""")

    section("viewer", "Repository Viewer", """\
Some information about Critic's repository viewers and its peculiarities
compared to \"normal\" git repository viewers such as gitk and cgit.""")

    section("reconfigure", "Reconfiguring Critic", """\
Information about the various per-user configuration options that Critic
supports.""")

    section("rebase", "Rebasing Reviews", """\
Details on what kind of rebase operations are supported on review
branches, how to convince Critic to accept non-fast-forward updates, and
some things you really should make sure not to do.""")

    if configuration.extensions.ENABLED:
        section("extensions", "Critic Extensions", """\
Description of the Critic Extensions mechanism.""")

        section("extensions-api", "Critic Extensions API", """\
Description of the script API available to Critic Extensions.""")

    if user.hasRole(db, "administrator"):
        section("administration", "System Administration", """\
Information about various Critic system administration tasks.""")

        section("customization", "System Customization", """\
Information about Critic system customization hooks.""")

def renderTutorial(req, db, user):
    item = req.getParameter("item", None)

    document = htmlutils.Document(req)
    document.setBase(None)
    document.setTitle("Tutorials")

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, current_page=None if item else "tutorial")

    document.addExternalStylesheet("resource/tutorial.css")
    document.addExternalScript("resource/tutorial.js")
    document.addInternalStylesheet("div.main table td.text { %s }" % user.getPreference(db, "style.tutorialFont"))

    target = body.div("main")

    items = { "request": "requesting",
              "review": "reviewing",
              "filters": "filters",
              "viewer": "repository",
              "rebase": "rebasing",
              "reconfigure": "reconfiguring",
              "checkbranch": "checkbranch",
              "administration": "administration",
              "customization": "customization" }

    if configuration.extensions.ENABLED:
        items.update({ "extensions": "extensions",
                       "extensions-api": "extensions-api" })

    if item in items:
        renderFromFile(db, target, items[item])
    else:
        renderSections(db, user, target)

    return document
