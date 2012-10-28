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
import htmlutils
import gitutils

import page.utils
import review.utils as review_utils
import log.commitset

def renderFilterChanges(req, db, user):
    review_id = page.utils.getParameter(req, "review", filter=int)
    first_sha1 = page.utils.getParameter(req, "first", None)
    last_sha1 = page.utils.getParameter(req, "last", None)

    cursor = db.cursor()

    review = dbutils.Review.fromId(db, review_id)

    root_directories = {}
    root_files = {}

    def processFile(file_id):
        components = dbutils.describe_file(db, file_id).split("/")
        directories, files = root_directories, root_files
        for directory_name in components[:-1]:
            directories, files = directories.setdefault(directory_name, ({}, {}))
        files[components[-1]] = file_id

    if first_sha1 and last_sha1:
        sha1 = last_sha1
        changesets = []

        cursor.execute("""SELECT commits.sha1
                            FROM commits
                            JOIN changesets ON (changesets.child=commits.id)
                            JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                           WHERE reviewchangesets.review=%s""",
                       (review.id,))

        first_commit = gitutils.Commit.fromSHA1(db, review.repository, first_sha1)
        last_commit = gitutils.Commit.fromSHA1(db, review.repository, last_sha1)

        if len(first_commit.parents) != 1:
            raise page.utils.DisplayMessage("Filtering failed!", "First selected commit is a merge commit.  Please go back and select a different range of commits.", review=review)

        from_commit = gitutils.Commit.fromSHA1(db, review.repository, first_commit.parents[0])
        to_commit = last_commit

        commits = log.commitset.CommitSet.fromRange(db, from_commit, to_commit)

        if not commits:
            raise page.utils.DisplayMessage("Filtering failed!", "The range of commits selected includes merges with ancestors not included in the range.  Please go back and select a different range of commits.", review=review)

        cursor.execute("""SELECT DISTINCT reviewfiles.file
                            FROM reviewfiles
                            JOIN changesets ON (changesets.id=reviewfiles.changeset)
                            JOIN commits ON (commits.id=changesets.child)
                           WHERE reviewfiles.review=%s
                             AND commits.sha1=ANY (%s)""",
                       (review.id, [commit.sha1 for commit in commits]))
    else:
        cursor.execute("SELECT DISTINCT file FROM reviewfiles WHERE review=%s", (review.id,))

    for (file_id,) in cursor:
        processFile(file_id)

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, lambda target: review_utils.renderDraftItems(db, user, review, target), extra_links=[("r/%d" % review.id, "Back to Review", True)])

    document.addExternalStylesheet("resource/filterchanges.css")
    document.addExternalScript("resource/filterchanges.js")
    document.addInternalScript(user.getJS())
    document.addInternalScript(review.getJS())

    if first_sha1 and last_sha1:
        document.addInternalScript("var commitRange = { first: %s, last: %s };" % (htmlutils.jsify(first_sha1), htmlutils.jsify(last_sha1)))
    else:
        document.addInternalScript("var commitRange = null;")

    target = body.div("main")

    basic = target.table('filter paleyellow', align='center', cellspacing=0)
    basic.col(width='10%')
    basic.col(width='60%')
    basic.col(width='30%')
    row = basic.tr("header")
    row.td('h1', colspan=2).h1().text("Filter Changes")
    row.td('h1 button').button("display").text("Display Diff")

    row = basic.tr("headings")
    row.td("select").text("Include")
    row.td("path").text("Path")
    row.td().text()

    def outputDirectory(base, name, directories, files):
        if name:
            level = base.count("/")
            row = basic.tr("directory", critic_level=level)
            row.td("select").input(type="checkbox")
            if level > 1:
                row.td("path").preformatted().innerHTML((" " * (len(base) - 2)) + "&#8230;/" + name + "/")
            else:
                row.td("path").preformatted().innerHTML(base + name + "/")
            row.td().text()
        else:
            level = 0

        for directory_name in sorted(directories.keys()):
            outputDirectory(base + name + "/" if name else "", directory_name, directories[directory_name][0], directories[directory_name][1])

        for file_name in sorted(files.keys()):
            row = basic.tr("file", critic_file_id=files[file_name], critic_level=level + 1)
            row.td("select").input(type="checkbox")
            row.td("path").preformatted().innerHTML((" " * (len(base + name) - 1)) + "&#8230;/" + htmlutils.htmlify(file_name))
            row.td().text()

    outputDirectory("", "", root_directories, root_files)

    row = basic.tr("footer")
    row.td('spacer', colspan=3)

    row = basic.tr("footer")
    row.td('button', colspan=3).button("display").text("Display Diff")

    if user.getPreference(db, "ui.keyboardShortcuts"):
        page.utils.renderShortcuts(body, "filterchanges")

    return document
