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
    batch_id = req.getParameter("batch", None, filter=int)
    review_id = req.getParameter("review", None, filter=int)

    cursor = db.cursor()

    if batch_id is None and review_id is None:
        return page.utils.displayMessage(db, req, user, "Missing argument: 'batch'")

    if batch_id:
        cursor.execute("SELECT review, uid, comment FROM batches WHERE id=%s", (batch_id,))

        row = cursor.fetchone()
        if not row:
            raise page.utils.DisplayMessage("Invalid batch ID: %d" % batch_id)

        review_id, author_id, chain_id = row
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

    page.utils.generateHeader(body, db, user, lambda target: review_utils.renderDraftItems(db, user, review, target), extra_links=[("r/%d" % review.id, "Back to Review")])

    document.addExternalStylesheet("resource/showreview.css")
    document.addExternalStylesheet("resource/showbatch.css")
    document.addExternalStylesheet("resource/review.css")
    document.addExternalStylesheet("resource/comment.css")
    document.addExternalScript("resource/review.js")
    document.addExternalScript("resource/comment.js")
    document.addInternalScript(user.getJS())
    document.addInternalScript(review.getJS())

    if batch_chain:
        document.addInternalScript("commentChainById[%d] = %s;" % (batch_chain.id, batch_chain.getJSConstructor()))

    target = body.div("main")

    table = target.table('paleyellow basic comments', align='center')
    table.col(width='10%')
    table.col(width='80%')
    table.col(width='10%')
    table.tr().td('h1', colspan=3).h1().text("Review by %s" % htmlify(author.fullname))

    if batch_chain:
        batch_chain.loadComments(db, user)

        row = table.tr("line")
        row.td("heading").text("Comment:")
        row.td("value").preformatted().div("text").text(htmlify(batch_chain.comments[0].comment))
        row.td("status").text()

    def renderFiles(title, cursor):
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

            row = table.tr("line")
            row.td("heading").text(title)

            files_table = row.td().table("files callout")
            headers = files_table.thead().tr()
            headers.th("path").text("Changed Files")
            headers.th("lines", colspan=2).text("Lines")

            files = files_table.tbody()
            for path, delete_count, insert_count in zip(paths, deleted, inserted):
                file = files.tr()
                file.td("path").preformatted().innerHTML(path)
                file.td("lines").preformatted().text("-%d" % delete_count if delete_count else None)
                file.td("lines").preformatted().text("+%d" % insert_count if insert_count else None)

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
                         AND reviewfilechanges.to_state='reviewed'
                    GROUP BY reviewfiles.file""" % condition("reviewfilechanges"))
    renderFiles("Reviewed:", cursor)

    cursor.execute("""SELECT reviewfiles.file, SUM(deleted), SUM(inserted)
                        FROM reviewfiles
                        JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)
                       WHERE %s
                         AND reviewfilechanges.to_state='pending'
                    GROUP BY reviewfiles.file""" % condition("reviewfilechanges"))
    renderFiles("Unreviewed:", cursor)

    def renderChains(title, cursor, replies):
        all_chains = [review_comment.CommentChain.fromId(db, chain_id, user, review=review)
                      for (chain_id,) in cursor]

        if not all_chains:
            return

        for chain in all_chains:
            chain.loadComments(db, user)

        issue_chains = list(filter(lambda chain: chain.type == "issue", all_chains))
        draft_issues = list(filter(lambda chain: chain.state == "draft", issue_chains))
        open_issues = list(filter(lambda chain: chain.state == "open", issue_chains))
        addressed_issues = list(filter(lambda chain: chain.state == "addressed", issue_chains))
        closed_issues = list(filter(lambda chain: chain.state == "closed", issue_chains))
        note_chains = list(filter(lambda chain: chain.type == "note", all_chains))
        draft_notes = list(filter(lambda chain: chain.state == "draft" and chain != batch_chain, note_chains))
        open_notes = list(filter(lambda chain: chain.state == "open" and chain != batch_chain, note_chains))

        def renderChains(target, chains):
            for chain in chains:
                row = target.tr("comment")
                row.td("author").text(chain.user.fullname)
                row.td("title").a(href="showcomment?chain=%d" % chain.id).innerHTML(chain.leader())
                row.td("when").text(chain.when())

        def showcomments(filter_param):
            params = { "review": review.id, "filter": filter_param }
            if batch_id:
                params["batch"] = batch_id
            return htmlutils.URL("/showcomments", **params)

        if draft_issues or open_issues or addressed_issues or closed_issues:
            h2 = table.tr().td("h2", colspan=3).h2().text(title)
            if len(draft_issues) + len(open_issues) + len(addressed_issues) + len(closed_issues) > 1:
                h2.a(href=showcomments("issues")).text("[display all]")

            if draft_issues:
                h3 = table.tr(id="draft-issues").td("h3", colspan=3).h3().text("Draft issues")
                if len(draft_issues) > 1:
                    h3.a(href=showcomments("draft-issues")).text("[display all]")
                renderChains(table, draft_issues)

            if batch_id is not None or replies:
                if open_issues:
                    h3 = table.tr(id="open-issues").td("h3", colspan=3).h3().text("Still open issues")
                    if batch_id and len(open_issues) > 1:
                        h3.a(href=showcomments("open-issues")).text("[display all]")
                    renderChains(table, open_issues)

                if addressed_issues:
                    h3 = table.tr(id="addressed-issues").td("h3", colspan=3).h3().text("Now addressed issues")
                    if batch_id and len(addressed_issues) > 1:
                        h3.a(href=showcomments("addressed-issues")).text("[display all]")
                    renderChains(table, addressed_issues)

                if closed_issues:
                    h3 = table.tr(id="closed-issues").td("h3", colspan=3).h3().text("Now closed issues")
                    if batch_id and len(closed_issues) > 1:
                        h3.a(href=showcomments("closed-issues")).text("[display all]")
                    renderChains(table, closed_issues)

        if draft_notes or open_notes:
            h2 = table.tr().td("h2", colspan=3).h2().text(title)
            if len(draft_notes) + len(open_notes) > 1:
                h2.a(href=showcomments("notes")).text("[display all]")

            if draft_notes:
                h3 = table.tr(id="draft-notes").td("h3", colspan=3).h3().text("Draft notes")
                if len(draft_notes) > 1:
                    h3.a(href=showcomments("draft-notes")).text("[display all]")
                renderChains(table, draft_notes)

            if open_notes:
                h3 = table.tr(id="notes").td("h3", colspan=3).h3().text("Notes")
                if batch_id and len(open_notes) > 1:
                    h3.a(href=showcomments("open-notes")).text("[display all]")
                renderChains(table, open_notes)

    cursor.execute("SELECT id FROM commentchains WHERE %s AND type='issue'" % condition("commentchains"))

    renderChains("Raised issues", cursor, False)

    cursor.execute("""SELECT commentchains.id
                        FROM commentchains
                        JOIN commentchainchanges ON (commentchainchanges.chain=commentchains.id)
                       WHERE %s
                         AND to_state='closed'""" % condition("commentchainchanges"))

    renderChains("Resolved issues", cursor, False)

    cursor.execute("""SELECT commentchains.id
                        FROM commentchains
                        JOIN commentchainchanges ON (commentchainchanges.chain=commentchains.id)
                       WHERE %s
                         AND to_state='open'""" % condition("commentchainchanges"))

    renderChains("Reopened issues", cursor, False)

    cursor.execute("""SELECT commentchains.id
                        FROM commentchains
                        JOIN commentchainchanges ON (commentchainchanges.chain=commentchains.id)
                       WHERE %s
                         AND to_type='issue'""" % condition("commentchainchanges"))

    renderChains("Converted into issues", cursor, False)

    cursor.execute("""SELECT commentchains.id
                        FROM commentchains
                        JOIN commentchainchanges ON (commentchainchanges.chain=commentchains.id)
                       WHERE %s
                         AND to_type='note'""" % condition("commentchainchanges"))

    renderChains("Converted into notes", cursor, False)

    cursor.execute("SELECT id FROM commentchains WHERE %s AND type='note'" % condition("commentchains"))

    renderChains("Written notes", cursor, False)

    cursor.execute("""SELECT commentchains.id
                        FROM commentchains
                        JOIN comments ON (comments.chain=commentchains.id)
                       WHERE %s
                         AND comments.id!=commentchains.first_comment""" % condition("comments"))

    renderChains("Replied to", cursor, True)

    return document
