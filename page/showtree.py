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

import dbutils
import gitutils
import page.utils
import htmlutils

import os.path
import stat

def renderShowTree(req, db, user):
    cursor = db.cursor()

    sha1 = req.getParameter("sha1")
    path = req.getParameter("path", "/")
    review_id = req.getParameter("review", None, filter=int)

    if path[0] == '/':
        full_path = path
        if path != "/": path = path[1:]
    else:
        full_path = "/" + path
        if not path: path = "/"

    if review_id is None:
        review = None
        review_arg = ""
        repository_arg = req.getParameter("repository", "")
        if repository_arg:
            repository = gitutils.Repository.fromParameter(db, repository_arg)
        else:
            repository = gitutils.Repository.fromSHA1(db, sha1)
        repository_arg = "&repository=%d" % repository.id
    else:
        review = dbutils.Review.fromId(db, review_id)
        review_arg = "&review=%d" % review_id
        repository_arg = ""
        repository = review.repository

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    extra_links = []

    if review:
        extra_links.append(("r/%d" % review.id, "Back to Review"))

    page.utils.generateHeader(body, db, user, extra_links=extra_links)

    document.addExternalStylesheet("resource/showtree.css")

    target = body.div("main")

    table = target.table("tree paleyellow", align="center", cellspacing=0)
    table.col(width="10%")
    table.col(width="60%")
    table.col(width="20%")

    thead = table.thead()
    h1 = thead.tr().td('h1', colspan=3).h1()

    if path == "/":
        h1.text("/")
    else:
        h1.a("root", href="showtree?sha1=%s&path=/%s%s" % (sha1, review_arg, repository_arg)).text("root")
        h1.span().text('/')

        components = path.split("/")
        for index, component in enumerate(components[:-1]):
            h1.a(href="showtree?sha1=%s&path=%s%s%s" % (sha1, "/".join(components[:index + 1]), review_arg, repository_arg)).text(component)
            h1.span().text('/')

        h1.text(components[-1])

    row = thead.tr()
    row.td('mode').text("Mode")
    row.td('name').text("Name")
    row.td('size').text("Size")

    tree = gitutils.Tree.fromPath(gitutils.Commit.fromSHA1(db, repository, sha1), full_path)

    def compareEntries(a, b):
        if a.type != b.type:
            if a.type == "tree": return -1
            else: return 1
        else:
            return cmp(a.name, b.name)

    tbody = table.tbody()

    for entry in sorted(tree, cmp=compareEntries):
        if entry.type == "blob": url = "showfile?sha1=%s&path=%s%s%s" % (sha1, os.path.join(path, entry.name), review_arg, repository_arg)
        else: url = "showtree?sha1=%s&path=%s%s%s" % (sha1, os.path.join(path, entry.name), review_arg, repository_arg)

        row = tbody.tr(entry.type)
        row.td('mode').text(str(entry.mode))

        if stat.S_ISLNK(entry.mode):
            cell = row.td('link', colspan=2)
            cell.span('name').text(entry.name)
            cell.text(' -> ')
            cell.span('target').text(repository.fetch(entry.sha1).data)
        elif entry.type == "commit":
            row.td('name').text("%s (%s)" % (entry.name, entry.sha1))
            row.td('size').text(entry.size)
        else:
            row.td('name').a(href=url).text(entry.name)
            row.td('size').text(entry.size)

    return document
