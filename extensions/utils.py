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
import page.utils
import textformatting

def renderTutorial(db, user, source):
    document = htmlutils.Document()

    document.addExternalStylesheet("resource/tutorial.css")
    document.addExternalScript("resource/tutorial.js")
    document.addInternalStylesheet("div.main table td.text { %s }" % user.getPreference(db, "style.tutorialFont"))

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user)

    table = body.div("main").table("paleyellow", align="center")
    textformatting.renderFormatted(db, user, table, source.splitlines(), toc=True)

    return str(document)
