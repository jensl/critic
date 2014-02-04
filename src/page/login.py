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

import page
import page.utils
import auth
import configuration
import request

from page.parameters import Optional

class LoginHandler(page.Page.Handler):
    def __init__(self, target="/", optional="no"):
        super(LoginHandler, self).__init__()
        self.target = target
        self.optional = optional == "yes"

    def generateHeader(self):
        self.document.addExternalStylesheet("resource/login.css")
        self.document.addExternalScript("resource/login.js")

    def generateContent(self):
        if not self.user.isAnonymous():
            raise page.utils.MovedTemporarily(self.target, True)

        self.request.ensureSecure()

        if configuration.base.AUTHENTICATION_MODE != "critic":
            raise request.DoExternalAuthentication(
                configuration.base.AUTHENTICATION_MODE, self.target)

        self.document.setTitle("Sign in")

        def render(target):
            redirect_url = "redirect?" + urllib.urlencode(
                { "target": self.target })

            form = target.form(name="login", method="POST", action=redirect_url)
            table = form.table("login callout", align="center")

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

            providers = []

            for name, provider in auth.PROVIDERS.items():
                providers.append((provider.getTitle(), name))

            if providers:
                table.tr("separator1").td(colspan=2)
                table.tr("separator2").td(colspan=2)

                external = table.tr("external").td(colspan=2)
                first = True

                for title, name in sorted(providers):
                    div = external.div("provider")
                    url = "/externalauth/%s?%s" % (name, urllib.urlencode(
                            { "target": self.target }))
                    if first:
                        div.text("Sign in using your ")
                        first = False
                    else:
                        div.text("or ")
                    div.a(href=url).text(title)

            if configuration.base.ALLOW_USER_REGISTRATION:
                table.tr("separator1").td(colspan=2)
                table.tr("separator2").td(colspan=2)

                register = table.tr("register").td(colspan=2)

                register.text("New to this system? ")
                register.a(href="/createuser").text("Create a user")
                register.text(" to start using it.")

            if self.optional:
                table.tr("separator1").td(colspan=2)
                table.tr("separator2").td(colspan=2)

                row = table.tr("continue")
                row.td(colspan=2).a(href=self.target).innerHTML(
                    "&#8230; or, continue anonymously")

        paleyellow = page.utils.PaleYellowTable(self.body, "Sign in")
        paleyellow.addCentered(render)

class Login(page.Page):
    def __init__(self):
        super(Login, self).__init__("login",
                                    { "target": Optional(str),
                                      "optional": Optional(str) },
                                    LoginHandler)
