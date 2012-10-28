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

def renderSections(target):
    table = target.table("paleyellow", align="center")
    table.tr("h1").td("h1").h1().text("Tutorial")

    table.tr("h2").td("h2").div().h2().text("Requesting a Review")
    table.tr("text").td("text").div().text("Introduction to the different ways of requesting a review of changes in Critic.  You'll be able to request a review of your bug fix in 10 seconds, using your favourite git client!  (Though it'll take you more than 10 seconds to read all the text&#8230;)", cdata=True)
    table.tr("goto").td("goto").div().a(href="tutorial?item=request").text("Learn More")

    table.tr("h2").td("h2").div().h2().text("Reviewing Changes")
    table.tr("text").td("text").div().text("Introduction to the process of reviewing changes in Critic.  Covers the basic concepts, marking changes as reviewed and raising issues, and some other things.  Useful information both for reviewers and for those requesting the reviews.")
    table.tr("goto").td("goto").div().a(href="tutorial?item=review").text("Learn More")

    table.tr("h2").td("h2").div().h2().text("Repository Viewer")
    table.tr("text").td("text").div().text("Some information about Critic's repository viewers and its peculiarities compared to \"normal\" git repository viewers such as gitk and cgit.")
    table.tr("goto").td("goto").div().a(href="tutorial?item=viewer").text("Learn More")

    table.tr("h2").td("h2").div().h2().text("Reconfiguring Critic")
    table.tr("text").td("text").div().text("Information about the various per-user configuration options that Critic supports.")
    table.tr("goto").td("goto").div().a(href="tutorial?item=reconfigure").text("Learn More")

    table.tr("h2").td("h2").div().h2().text("Rebasing Reviews")
    table.tr("text").td("text").div().text("Details on what kind of rebase operations are supported on review branches, how to convince Critic to accept non-fast-forward updates, and some things you really should make sure not to do.")
    table.tr("goto").td("goto").div().a(href="tutorial?item=rebase").text("Learn More")

    if configuration.extensions.ENABLED:
        table.tr("h2").td("h2").div().h2().text("Critic Extensions")
        table.tr("text").td("text").div().text("Description of the Critic Extensions mechanism.")
        table.tr("goto").td("goto").div().a(href="tutorial?item=extensions").text("Learn More")

        table.tr("h2").td("h2").div().h2().text("Critic Extensions API")
        table.tr("text").td("text").div().text("Description of the script API available to Critic Extensions.")
        table.tr("goto").td("goto").div().a(href="tutorial?item=extensions-api").text("Learn More")

def renderTutorial(req, db, user):
    item = req.getParameter("item", None)

    document = htmlutils.Document(req)
    document.setBase(None)

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, current_page="tutorial")

    document.addExternalStylesheet("resource/tutorial.css")
    document.addExternalScript("resource/tutorial.js")
    document.addInternalStylesheet("div.main table td.text { %s }" % user.getPreference(db, "style.tutorialFont"))

    target = body.div("main")

    if item == "request":
        renderFromFile(db, target, "requesting")
    elif item == "review":
        renderFromFile(db, target, "reviewing")
    elif item == "viewer":
        renderFromFile(db, target, "repository")
    elif item == "rebase":
        renderFromFile(db, target, "rebasing")
    elif item == "reconfigure":
        renderFromFile(db, target, "reconfiguring")
    elif item == "gettingstarted":
        renderFromFile(db, target, "gettingstarted")
    elif item == "checkbranch":
        renderFromFile(db, target, "checkbranch")
    elif item == "extensions" and configuration.extensions.ENABLED:
        renderFromFile(db, target, "extensions")
    elif item == "extensions-api" and configuration.extensions.ENABLED:
        renderFromFile(db, target, "extensions-api")
    else:
        renderSections(target)

    return document
