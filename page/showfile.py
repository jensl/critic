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
import os.path
import htmlutils
import diff
import reviewing.utils as review_utils
import reviewing.comment as review_comment

from syntaxhighlight.request import requestHighlights

def renderShowFile(req, db, user):
    cursor = db.cursor()

    sha1 = req.getParameter("sha1")
    path = req.getParameter("path")
    line = req.getParameter("line", None)
    review_id = req.getParameter("review", None, filter=int)

    default_tabify = "yes" if user.getPreference(db, "commit.diff.visualTabs") else "no"
    tabify = req.getParameter("tabify", default_tabify) == "yes"

    if line is None:
        first, last = None, None
    else:
        if "-" in line:
            first, last = map(int, line.split("-"))
        else:
            first = last = int(line)

        context = req.getParameter("context", user.getPreference(db, "commit.diff.contextLines"), int)

        first_with_context = max(1, first - context)
        last_with_context = last + context

    if user.getPreference(db, "commit.diff.compactMode"): default_compact = "yes"
    else: default_compact = "no"

    compact = req.getParameter("compact", default_compact) == "yes"

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

    if review:
        page.utils.generateHeader(body, db, user, lambda target: review_utils.renderDraftItems(db, user, review, target), extra_links=[("r/%d" % review.id, "Back to Review", True)])
    else:
        page.utils.generateHeader(body, db, user)

    document.addExternalStylesheet("resource/showfile.css")
    document.addInternalStylesheet(htmlutils.stripStylesheet(user.getResource(db, "syntax.css")[1], compact))

    commit = gitutils.Commit.fromSHA1(db, repository, sha1)
    file_sha1 = commit.getFileSHA1(full_path)
    file_id = dbutils.find_file(db, path=path)

    file = diff.File(file_id, path, None, file_sha1, repository)

    # A new file ID might have been added to the database, so need to commit.
    db.commit()

    if file.canHighlight():
        requestHighlights(repository, { file.new_sha1: (file.path, file.getLanguage()) })

    file.loadNewLines(True, request_highlight=True)

    if review:
        document.addInternalScript(user.getJS())
        document.addInternalScript(review.getJS())
        document.addInternalScript("var changeset = { parent: { id: %(id)d, sha1: %(sha1)r }, child: { id: %(id)d, sha1: %(sha1)r } };" % { 'id': commit.getId(db), 'sha1': commit.sha1 })
        document.addInternalScript("var files = { %(id)d: { new_sha1: %(sha1)r }, %(sha1)r: { id: %(id)d, side: 'n' } };" % { 'id': file_id, 'sha1': file_sha1 })
        document.addExternalStylesheet("resource/review.css")
        document.addExternalScript("resource/review.js")

        cursor.execute("""SELECT DISTINCT id
                          FROM commentchains
                            JOIN commentchainlines ON (id=chain)
                          WHERE review=%s
                            AND file=%s
                            AND sha1=%s
                            AND ((commentchains.state!='draft' OR commentchains.uid=%s)
                                 AND commentchains.state!='empty')
                          GROUP BY id""",
                       [review.id, file_id, file_sha1, user.id])

        comment_chain_script = ""

        for (chain_id,) in cursor.fetchall():
            chain = review_comment.CommentChain.fromId(db, chain_id, user, review=review)
            chain.loadComments(db, user)

            comment_chain_script += "commentChains.push(%s);\n" % chain.getJSConstructor(file_sha1)

        if comment_chain_script:
            document.addInternalScript(comment_chain_script)

    document.addExternalStylesheet("resource/comment.css")
    document.addExternalScript("resource/comment.js")
    document.addExternalScript("resource/showfile.js")

    if tabify:
        document.addExternalStylesheet("resource/tabify.css")
        document.addExternalScript("resource/tabify.js")
        tabwidth = file.getTabWidth()
        indenttabsmode = file.getIndentTabsMode()

    if user.getPreference(db, "commit.diff.highlightIllegalWhitespace"):
        document.addInternalStylesheet(user.getResource(db, "whitespace.css")[1], compact)

    if first is not None:
        document.addInternalScript("var firstSelectedLine = %d, lastSelectedLine = %d;" % (first, last))

    target = body.div("main")

    if tabify:
        target.script(type="text/javascript").text("calculateTabWidth();")

    table = target.table('file show expanded paleyellow', align='center', cellspacing=0)

    columns = table.colgroup()
    columns.col('edge').empty()
    columns.col('linenr').empty()
    columns.col('line').empty()
    columns.col('middle').empty()
    columns.col('middle').empty()
    columns.col('line').empty()
    columns.col('linenr').empty()
    columns.col('edge').empty()

    thead = table.thead()
    cell = thead.tr().td('h1', colspan=8)
    h1 = cell.h1()

    h1.a("root", href="showtree?sha1=%s&path=/%s%s" % (sha1, review_arg, repository_arg)).text("root")
    h1.span().text('/')

    components = path.split("/")
    for index, component in enumerate(components[:-1]):
        h1.a(href="showtree?sha1=%s&path=%s%s%s" % (sha1, "/".join(components[:index + 1]), review_arg, repository_arg)).text(component)
        h1.span().text('/')

    if first is not None:
        h1.a(href="showfile?sha1=%s&path=%s%s%s" % (sha1, "/".join(components), review_arg, repository_arg)).text(components[-1])
    else:
        h1.text(components[-1])

    h1.span("right").a(href="/download/%s?repository=%s&sha1=%s" % (path, repository.name, file_sha1)).text("[download]")

    table.tbody('spacer top').tr('spacer top').td(colspan=8).text()

    tbody = table.tbody("lines")

    yield document.render(stop=tbody, pretty=not compact)

    for linenr, line in enumerate(file.newLines(True)):
        linenr = linenr + 1
        highlight_class = ""

        if first is not None:
            if not (first_with_context <= linenr <= last_with_context): continue
            if linenr == first:
                highlight_class += " first-selected"
            if linenr == last:
                highlight_class += " last-selected"

        if tabify:
            line = htmlutils.tabify(line, tabwidth, indenttabsmode)

        line = line.replace("\r", "<i class='cr'></i>")

        row = tbody.tr("line context single", id="f%do%dn%d" % (file.id, linenr, linenr))
        row.td("edge").text()
        row.td("linenr old").text(linenr)
        row.td("line single whole%s" % highlight_class, id="f%dn%d" % (file.id, linenr), colspan=4).innerHTML(line)
        row.td("linenr new").text(linenr)
        row.td("edge").text()

        if linenr % 500:
            yield document.render(stop=tbody, pretty=not compact)

    table.tbody('spacer bottom').tr('spacer bottom').td(colspan=8).text()

    yield document.render(pretty=not compact)
