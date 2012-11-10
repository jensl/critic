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

import urllib

import htmlutils
import page.utils

def renderLogin(req, db, user):
    target_url = req.getParameter("target", "/")

    if not user.isAnonymous():
        raise page.utils.MovedTemporarily(target_url or "/", True)

    document = htmlutils.Document(req)
    document.setTitle("Login")

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, current_page="login")

    document.addExternalStylesheet("resource/login.css")
    document.addExternalScript("resource/login.js")

    def render(target):
        form = target.form(name="login", method="POST", action="redirect?" + urllib.urlencode({ "target": target_url }))
        table = form.table("login", align="center")

        row = table.tr("status disabled")
        row.td(colspan=2).text()

        row = table.tr("username")
        row.td("key").text("Username:")
        row.td("value").input("username", name="username", autofocus="autofocus")

        row = table.tr("password")
        row.td("key").text("Password:")
        row.td("value").input("password", name="password", type="password")

        row = table.tr("login")
        row.td(colspan=2).input("login", type="submit", value="Sign in")

    paleyellow = page.utils.PaleYellowTable(body, "Sign in")
    paleyellow.addCentered(render)

    return document
