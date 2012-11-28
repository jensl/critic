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
import reviewing.comment as review_comment
import reviewing.utils as review_utils
import htmlutils
import diff

from htmlutils import jsify, htmlify

def renderShowBatch(req, db, user):
    batch_id = page.utils.getParameter(req, "batch", None, filter=int)
    review_id = page.utils.getParameter(req, "review", None, filter=int)

    cursor = db.cursor()

    if batch_id is None and review_id is None:
        return page.utils.displayMessage(db, req, user, "Missing argument: 'batch'")

    if batch_id:
        cursor.execute("SELECT review, uid, comment FROM batches WHERE id=%s", (batch_id,))
        review_id, author_id, chain_id = cursor.fetchone()
        author = dbutils.User.fromId(db, author_id)
    else:
        chain_id = None
        author = user

    review = dbutils.Review.fromId(db, review_id)

    if chain_id:
        batch_chain = review_comment.CommentChain.fromId(db, chain_id, user, review=review)
        batch_chain.loadComments(db, user)
    else:
        batch_chain = None

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, lambda target: review_utils.renderDraftItems(db, user, review, target), extra_links=[("r/%d" % review.id, "Back to Review", True)])

    document.addExternalStylesheet("resource/showbatch.css")
    document.addExternalStylesheet("resource/showreview.css")
    document.addExternalStylesheet("resource/review.css")
    document.addExternalStylesheet("resource/comment.css")
    document.addExternalScript("resource/review.js")
    document.addExternalScript("resource/comment.js")
    document.addInternalScript(user.getJS())
    document.addInternalScript(review.getJS())

    if batch_chain:
        document.addInternalScript("commentChainById[%d] = %s;" % (batch_chain.id, batch_chain.getJSConstructor()))

    target = body.div("main")

    basic = target.table('paleyellow basic', align='center')
    basic.col(width='10%')
    basic.col(width='80%')
    basic.col(width='10%')
    basic.tr().td('h1', colspan=3).h1().text("Review by %s" % htmlify(author.fullname))

    if batch_chain:
        batch_chain.loadComments(db, user)

        row = basic.tr("line")
        row.td("heading").text("Comment:")
        row.td("value").preformatted().div("text").text(htmlify(batch_chain.comments[0].comment))
        row.td("status").text()

    def renderFiles(title):
        files = []

        for file_id, delete_count, insert_count in cursor.fetchall():
            files.append((dbutils.describe_file(db, file_id), delete_count, insert_count))

        paths = []
        deleted = []
        inserted = []

        for path, delete_count, insert_count in sorted(files):
            paths.append(path)
            deleted.append(delete_count)
            inserted.append(insert_count)

        if paths:
            diff.File.eliminateCommonPrefixes(paths)

            row = basic.tr("line")
            row.td("heading").text(title)

            table = row.td("files").table("files")
            headers = table.thead().tr()
            headers.th("path").text("Changed Files")
            headers.th(colspan=2).text("Lines")

            files = table.tbody()
            for path, delete_count, insert_count in zip(paths, deleted, inserted):
                file = files.tr()
                file.td("path").preformatted().innerHTML(path)
                file.td().preformatted().text(delete_count and "-%d" % delete_count or "")
                file.td().preformatted().text(delete_count and "+%d" % insert_count or "")

            row.td("status").text()

    def condition(table_name):
        if batch_id:
            return "%s.batch=%d" % (table_name, batch_id)
        else:
            return "review=%d AND %s.batch IS NULL AND %s.uid=%d" % (review.id, table_name, table_name, author.id)

    cursor.execute("""SELECT reviewfiles.file, SUM(deleted), SUM(inserted)
                        FROM reviewfiles
                        JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)
                       WHERE %s
                         AND reviewfilechanges.to='reviewed'
                    GROUP BY reviewfiles.file""" % condition("reviewfilechanges"))
    renderFiles("Reviewed:")

    cursor.execute("""SELECT reviewfiles.file, SUM(deleted), SUM(inserted)
                        FROM reviewfiles
                        JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)
                       WHERE %s
                         AND reviewfilechanges.to='pending'
                    GROUP BY reviewfiles.file""" % condition("reviewfilechanges"))
    renderFiles("Unreviewed:")

    def renderChains(title, replies):
        all_chains = [review_comment.CommentChain.fromId(db, id, user, review=review) for (id,) in rows]

        for chain in all_chains: chain.loadComments(db, user)

        issue_chains = filter(lambda chain: chain.type == "issue", all_chains)
        draft_issues = filter(lambda chain: chain.state == "draft", issue_chains)
        open_issues = filter(lambda chain: chain.state == "open", issue_chains)
        addressed_issues = filter(lambda chain: chain.state == "addressed", issue_chains)
        closed_issues = filter(lambda chain: chain.state == "closed", issue_chains)
        note_chains = filter(lambda chain: chain.type == "note", all_chains)
        draft_notes = filter(lambda chain: chain.state == "draft" and chain != batch_chain, note_chains)
        open_notes = filter(lambda chain: chain.state == "open" and chain != batch_chain, note_chains)

        def renderChains(target, chains):
            for chain in chains:
                row = target.tr("comment")
                row.td("author").text(chain.user.fullname)
                row.td("title").a(href="showcomment?chain=%d" % chain.id).innerHTML(chain.leader())
                row.td("when").text(chain.when())

        if draft_issues or open_issues or addressed_issues or closed_issues:
            chains = target.table("paleyellow comments", align="center", cellspacing=0)
            chains.tr().td("h1", colspan=3).h1().text(title)

            if draft_issues:
                chains.tr(id="draft-issues").td("h2", colspan=3).h2().text("Draft Issues").a(href="showcomments?review=%d&filter=draft-issues" % review.id).text("[display all]")
                renderChains(chains, draft_issues)

            if batch_id is not None or replies:
                if open_issues:
                    h2 = chains.tr(id="open-issues").td("h2", colspan=3).h2().text("Still Open Issues")
                    if batch_id:
                        h2.a(href="showcomments?review=%d&filter=open-issues&batch=%d" % (review.id, batch_id)).text("[display all]")
                    renderChains(chains, open_issues)

                if addressed_issues:
                    h2 = chains.tr(id="addressed-issues").td("h2", colspan=3).h2().text("Now Addressed Issues")
                    if batch_id:
                        h2.a(href="showcomments?review=%d&filter=addressed-issues&batch=%d" % (review.id, batch_id)).text("[display all]")
                    renderChains(chains, addressed_issues)

                if closed_issues:
                    h2 = chains.tr(id="closed-issues").td("h2", colspan=3).h2().text("Now Closed Issues")
                    if batch_id:
                        h2.a(href="showcomments?review=%d&filter=closed-issues&batch=%d" % (review.id, batch_id)).text("[display all]")
                    renderChains(chains, closed_issues)

        if draft_notes or open_notes:
            chains = target.table("paleyellow comments", align="center", cellspacing=0)
            chains.tr().td("h1", colspan=3).h1().text(title)

            if draft_notes:
                chains.tr(id="draft-notes").td("h2", colspan=3).h2().text("Draft Notes").a(href="showcomments?review=%d&filter=draft-notes" % review.id).text("[display all]")
                renderChains(chains, draft_notes)

            if open_notes:
                h2 = chains.tr(id="notes").td("h2", colspan=3).h2().text("Notes")
                if batch_id:
                    h2.a(href="showcomments?review=%d&filter=open-notes&batch=%d" % (review.id, batch_id)).text("[display all]")
                renderChains(chains, open_notes)

    cursor.execute("SELECT id FROM commentchains WHERE %s AND type='issue'" % condition("commentchains"))
    rows = cursor.fetchall()

    if rows: renderChains("Raised Issues", False)

    cursor.execute("SELECT id FROM commentchains WHERE %s AND type='note'" % condition("commentchains"))
    rows = cursor.fetchall()

    if rows: renderChains("Written Notes", False)

    cursor.execute("""SELECT commentchains.id
                        FROM commentchains
                        JOIN comments ON (comments.chain=commentchains.id)
                       WHERE %s
                         AND comments.id!=commentchains.first_comment""" % condition("comments"))
    rows = cursor.fetchall()

    if rows: renderChains("Replied To", True)

    return document
