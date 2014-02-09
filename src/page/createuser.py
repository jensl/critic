# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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
import page
import auth
import dbutils
import configuration

from page.parameters import Optional

class CreateUserHandler(page.Page.Handler):
    def __init__(self, target=None, username=None, email=None, fullname=None,
                 provider=None, account=None, token=None):
        super(CreateUserHandler, self).__init__()

        self.target = target
        self.username = username
        self.email = email
        self.fullname = fullname
        self.provider = provider
        self.account = account
        self.token = token

    def generateHeader(self):
        self.document.addExternalStylesheet("resource/createuser.css")
        self.document.addExternalScript("resource/createuser.js")

        if self.target:
            self.document.addInternalScript(
                "var target = %s;" % htmlutils.jsify(self.target))

    def generateContent(self):
        table = page.utils.PaleYellowTable(self.body, "Create user")

        if self.provider and self.token and self.provider in auth.PROVIDERS:
            provider = auth.PROVIDERS[self.provider]
            if not provider.validateToken(self.db, self.account, self.token):
                raise page.utils.DisplayMessage("Invalid OAuth2 token")
            allow_user_registration = \
                provider.configuration.get("allow_user_registration", False)
        else:
            provider = None
            allow_user_registration = configuration.base.ALLOW_USER_REGISTRATION

        if not allow_user_registration:
            administrators = dbutils.getAdministratorContacts(
                self.db, as_html=True)
            raise page.utils.DisplayMessage(
                title="User registration not enabled",
                body=(("<p>The administrator of this system has not enabled "
                       "registration of new users.</p>"
                       "<p>Contact %s if you want to use this system.</p>")
                      % administrators),
                html=True)

        def render(target):
            table = target.table("createuser", align="center")

            def header(label):
                row = table.tr("header")
                row.td(colspan=2).text(label)

            def item(key):
                row = table.tr("item")
                row.td("key").text("%s:" % key)
                return row.td("value")

            def button(class_name):
                row = table.tr("button")
                return row.td(colspan=2).button(class_name)

            def separator():
                table.tr("separator1").td(colspan=2)
                table.tr("separator2").td(colspan=2)

            if provider:
                self.document.addInternalScript(
                    "var external = { provider: %s, account: %s, token: %s };"
                    % (htmlutils.jsify(self.provider),
                       htmlutils.jsify(self.account),
                       htmlutils.jsify(self.token)))

                url = provider.getAccountURL(self.account)
                item(provider.getTitle()).a("external", href=url).text(self.account)
                separator()
            else:
                self.document.addInternalScript("var external = null;")

            message = table.tr("status disabled").td(colspan=2).div("message")

            if self.username:
                try:
                    dbutils.User.fromName(self.db, self.username)
                except dbutils.NoSuchUser:
                    try:
                        auth.validateUserName(self.username)
                    except auth.InvalidUserName as error:
                        message.u("Invalid user name")
                        message.br()
                        message.text(str(error))
                else:
                    message.text("A user named '%s' already exists!"
                                 % self.username)

            item("New user name").input(id="newusername", value=self.username, size=40)
            item("Display name").input(id="fullname", value=self.fullname, size=40)
            item("Email").input(id="email", value=self.email, size=40)

            if not provider:
                separator()

                item("Password").input(id="password1", type="password", size=40)
                item("Password (again)").input(id="password2", type="password", size=40)

            button("create").text("Create user")

        table.addCentered(render)

class CreateUser(page.Page):
    def __init__(self):
        super(CreateUser, self).__init__("createuser",
                                         { "target": Optional(str),
                                           "username": Optional(str),
                                           "email": Optional(str),
                                           "fullname": Optional(str),
                                           "provider": Optional(str),
                                           "account": Optional(str),
                                           "token": Optional(str) },
                                         CreateUserHandler)
