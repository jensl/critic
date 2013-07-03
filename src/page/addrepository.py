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
import os
import os.path
import signal
import configuration
import htmlutils
import dbutils

from subprocess import Popen as process, PIPE

def renderNewRepository(req, db, user):
    if not user.hasRole(db, "repositories"):
        raise page.utils.DisplayMessage(title="Not allowed!", body="Only users with the 'repositories' role can add new repositories.")

    cursor = db.cursor()

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user)

    document.addExternalStylesheet("resource/newrepository.css")
    document.addExternalScript("resource/newrepository.js")

    target = body.div("main")

    basic = target.table('information', align='center')
    basic.col(width='20%')
    basic.col(width='0')
    basic.col(width='40%')
    basic.col(width='40%')
    h1 = basic.tr().td('h1', colspan=4).h1().text("New Repository")

    row = basic.tr("name")
    row.td("heading").text("Short name:")
    row.td("prefix").text()
    row.td("value").input(name="name")
    row.td("suffix").text()

    row = basic.tr("help")
    row.td(colspan=4).text("Repository short name.")

    row = basic.tr("path")
    row.td("heading").text("Path:")
    row.td("prefix").text("%s:%s/" % (configuration.base.HOSTNAME, configuration.paths.GIT_DIR))
    row.td("value").input(name="path")
    row.td("suffix").text(".git")

    row = basic.tr("help")
    row.td(colspan=4).text("Path of repository on the Critic server.")

    row = basic.tr("remote")
    row.td("heading").text("Source repository:")
    row.td("prefix").text()
    row.td("value").input(name="remote")
    row.td("suffix").text("(optional)")

    row = basic.tr("help")
    row.td(colspan=4).text("Git URL of repository to mirror.")

    row = basic.tr("branch")
    row.td("heading").text("Source branch:")
    row.td("prefix").text()
    row.td("value").input(name="branch", value="master", disabled="disabled")
    row.td("suffix").text()

    row = basic.tr("help")
    row.td(colspan=4).text("This branch in the source repository is automatically mirrored in Critic's repository.")

    row = basic.tr("buttons")
    row.td(colspan=4).button("add").text("Add Repository")

    return document
