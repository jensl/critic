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

import functools

import request
import htmlutils
import page.utils
import page.parameters

class Page(object):
    def __init__(self, name, parameters, handler):
        self.name = name
        self.parameters = parameters
        self.handler = handler

    def __call__(self, req, db, user):
        parameters = {}

        for name, checker in self.parameters.items():
            if isinstance(checker, page.parameters.Optional):
                default = None
                checker = checker.actual
            else:
                default = request.NoDefault()

            is_list = isinstance(checker, page.parameters.ListOf)

            if is_list:
                checker = checker.actual

            if issubclass(checker, page.parameters.Stateful):
                checker = checker(req, db, user)

            try:
                value = req.getParameter(name, default, str if is_list else checker)
            except page.parameters.InvalidParameterValue as error:
                raise request.InvalidParameterValue(name, req.getParameter(name), error.expected)

            if value is not None:
                if is_list:
                    values = []
                    for item in value.split(","):
                        values.append(checker(item))
                    value = values

                parameters[name] = value

        return self.handler(**parameters).generate(self, req, db, user)

    class Handler(object):
        def __init__(self, review=None):
            self.review = review

        def setup(self, page, req, db, user):
            self.page = page
            self.request = req
            self.db = db
            self.user = user

        def generate(self, page, req, db, user):
            self.setup(page, req, db, user)

            self.document = htmlutils.Document(req)
            self.html = self.document.html()
            self.head = self.html.head()
            self.body = self.html.body()

            self._generateHeader()
            self.generateContent()
            self._generateFooter()

            return self.document

        def _generateHeader(self):
            page.utils.generateHeader(self.body, self.db, self.user,
                                      current_page=self.page.name,
                                      generate_right=self.getGenerateHeaderRight(),
                                      extra_links=self.getExtraLinks())
            self.generateHeader()

        def generateHeader(self):
            pass

        def generateContent(self):
            self.body.div("message").h1("center").text("Not implemented!")

        def _generateFooter(self):
            self.generateFooter()
            page.utils.generateFooter(self.body, self.db, self.user,
                                      current_page=self.page.name)

        def generateFooter(self):
            pass

        def getGenerateHeaderRight(self):
            if self.review:
                import reviewing.utils
                return functools.partial(reviewing.utils.renderDraftItems, self.db, self.user, self.review)

        def getExtraLinks(self):
            if self.review:
                return [("r/%d" % self.review.id, "Back to Review")]
            else:
                return []
