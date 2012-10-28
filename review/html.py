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
import gitutils
import dbutils
import log.html
import diff
import diff.context
import changeset.html as changeset_html
import changeset.utils as changeset_utils
import page.utils
import page.showcommit
import linkify

from time import strftime

def renderComments(db, target, user, chain, position, linkify):
    repository = chain.review.repository

    div_chain = target.div("comments %s" % position)

    def linkToCommit(commit):
        cursor.execute("SELECT 1 FROM commits JOIN changesets ON (child=commits.id) JOIN reviewchangesets ON (changeset=changesets.id) WHERE sha1=%s AND review=%s", (commit.sha1, review.id))
        if cursor.fetchone():
            return "%s/%s?review=%d" % (repository.name, commit.sha1, chain.review.id)
        return "%s/%s" % (repository.name, commit.sha1)

    for comment in chain.comments:
        div_comment = div_chain.div("comment%s" % (comment.state == "draft" and " draft" or ""), id="c%dc%d" % (chain.id, comment.id))

        div_header = div_comment.div("header")
        div_header.span("author").text("%s <%s>" % (comment.user.fullname, comment.user.email))
        div_header.text(" posted ")
        div_header.span("time").text(strftime("%Y-%m-%d %H:%M", comment.time.timetuple()))

        div_text = div_comment.div("text", id="c%dtext" % comment.id).preformatted()
        div_text.text(comment.comment, linkify=linkify, repository=repository)

    if chain.type == "issue" and chain.state not in ("draft", "open"):
        div_resolution = div_chain.div("resolution")

        if chain.state == "addressed":
            div_resolution.text("Addressed by ").a(href="showcommit?review=%d&sha1=%s" % (chain.review.id, chain.addressed_by.sha1)).text(chain.addressed_by.sha1[:8])

            if chain.closed_by:
                div_resolution.text(" (by %s)" % chain.closed_by.fullname)
        else:
            div_resolution.text("Resolved by " + chain.closed_by.fullname)

    div_buttons = div_chain.div("buttons")

    if (chain.state == "closed" or chain.addressed_by) and chain.type == "issue":
        div_buttons.button("reopen", onclick="commentChainById[%d].reopen(true);" % chain.id).text("Reopen Issue")

    if chain.type == "issue":
        if chain.state == "open":
            if not chain.type_is_draft:
                div_buttons.button("resolve", onclick="commentChainById[%d].resolve(null);" % chain.id).text("Resolve Issue")
        if chain.type_is_draft or user.getPreference(db, "ui.convertIssueToNote"):
            div_buttons.button("morph", onclick="commentChainById[%d].morph(null, this);" % chain.id).text("Convert %sto Note" % ("back " if chain.type_is_draft else ""))
    else:
        div_buttons.button("morph", onclick="commentChainById[%d].morph(null, this);" % chain.id).text("Convert %sto Issue" % ("back " if chain.type_is_draft else ""))

    if chain.comments[-1].state == "draft":
        div_buttons.button("edit", onclick="commentChainById[%d].editComment(commentChainById[%d].comments[%d], null);" % (chain.id, chain.id, len(chain.comments) - 1)).text("Edit")
        div_buttons.button("delete", onclick="commentChainById[%d].deleteComment(commentChainById[%d].comments[%d], null);" % (chain.id, chain.id, len(chain.comments) - 1)).text("Delete")
        reply_hidden = " hidden"
    else:
        reply_hidden = ""

    div_buttons.button("reply" + reply_hidden, onclick="commentChainById[%d].reply(null);" % chain.id).text("Reply")

    div_buttons.span("buttonscope buttonscope-comment")

def getCodeCommentChainChangeset(db, chain, original=False):
    if (chain.state != "addressed" or original) and chain.first_commit == chain.last_commit:
        # Comment against a single version of the file, not against a diff.
        return None, None
    elif chain.state == "addressed" and not original:
        parent = gitutils.Commit.fromSHA1(db, chain.review.repository, chain.addressed_by.parents[0])
        child = chain.addressed_by
    else:
        parent = chain.first_commit
        child = chain.last_commit

    return parent, child

def renderCodeCommentChain(db, target, user, review, chain, context_lines=3, compact=False, tabify=False, original=False, changeset=None, linkify=False):
    repository = review.repository

    old_sha1 = None
    new_sha1 = None
    chunks = None

    old = 1
    new = 2

    cursor = db.cursor()

    file_id = chain.file_id
    file_path = dbutils.describe_file(db, file_id)

    if (chain.state != "addressed" or original) and chain.first_commit == chain.last_commit:
        cursor.execute("SELECT sha1, first_line, last_line FROM commentchainlines WHERE chain=%s AND commit=%s", (chain.id, chain.first_commit.getId(db)))
        sha1, first_line, last_line = cursor.fetchone()

        file = diff.File(file_id, file_path, sha1, sha1, review.repository, chunks=[])
        file.loadNewLines(True)

        start = max(1, first_line - context_lines)
        end = min(file.newCount() + 1, last_line + context_lines)
        count = end + 1 - start

        lines = file.newLines(True)
        lines = [diff.Line(diff.Line.CONTEXT, start + index, lines[start + index - 1], start + index, lines[start + index - 1]) for index in range(count)]

        file.macro_chunks = [diff.MacroChunk([], lines)]

        use = new
        display_type = "new"
        commit_url_component = "sha1=%s" % chain.first_commit.sha1
    else:
        if chain.state == "addressed" and not original:
            parent = gitutils.Commit.fromSHA1(db, review.repository, chain.addressed_by.parents[0])
            child = chain.addressed_by
            use = old
        else:
            parent = chain.first_commit
            child = chain.last_commit

            if parent == child:
                if chain.origin == "old":
                    cursor.execute("""SELECT changesets.child
                                        FROM changesets, reviewchangesets
                                       WHERE changesets.parent=%s
                                         AND reviewchangesets.changeset=changesets.id
                                         AND reviewchangesets.review=%s""",
                                   [child.getId(db), review.id])

                    try:
                        child = gitutils.Commit.fromId(db, repository, cursor.fetchone()[0])
                    except:
                        parent = gitutils.Commit.fromSHA1(db, repository, child.parents[0])
                else:
                    parent = gitutils.Commit.fromSHA1(db, repository, child.parents[0])

            if chain.origin == "old": use = old
            else: use = new

        if parent.sha1 in child.parents and len(child.parents) == 1:
            commit = child
            from_commit = None
            to_commit = None
        else:
            commit = None
            from_commit = parent
            to_commit = child

        if changeset:
            assert ((changeset.parent == from_commit and changeset.child == to_commit)
                    if commit is None else
                    (changeset.parent.sha1 == commit.parents[0] and changeset.child == commit))
            assert changeset.getFile(file_id)
        else:
            changeset = changeset_utils.createChangeset(db, user, repository, commit=commit, from_commit=from_commit, to_commit=to_commit, filtered_file_ids=set((file_id,)))[0]

        file = changeset.getFile(file_id)

        if not file:
            if chain.state == "addressed" and not original:
                renderCodeCommentChain(db, target, user, review, chain, context_lines, compact, tabify, original=True)
                return
            else:
                raise

        # Commit so that the diff and its analysis, written to the database by createChangeset(),
        # can be reused later.
        db.commit()

        old_sha1 = file.old_sha1
        new_sha1 = file.new_sha1

        if use == old and old_sha1 == '0' * 40: use = new
        elif use == new and new_sha1 == '0' * 40: use = old

        if use == old: sha1 = old_sha1
        else: sha1 = new_sha1

        cursor.execute("SELECT first_line, last_line FROM commentchainlines WHERE chain=%s AND sha1=%s", [chain.id, sha1])

        first_line, last_line = cursor.fetchone()

        def readChunks():
            return [diff.Chunk(delete_offset, delete_count, insert_offset, insert_count, analysis=analysis, is_whitespace=is_whitespace)
                    for delete_offset, delete_count, insert_offset, insert_count, analysis, is_whitespace
                    in cursor.fetchall()]

        first_context_line = first_line - context_lines
        last_context_line = last_line + context_lines

        def includeChunk(chunk):
            if use == old: chunk_first_line, chunk_last_line = chunk.delete_offset, chunk.delete_offset + chunk.delete_count - 1
            else: chunk_first_line, chunk_last_line = chunk.insert_offset, chunk.insert_offset + chunk.insert_count - 1

            return chunk_last_line >= first_context_line and chunk_first_line <= last_context_line

        def lineFilter(line):
            if use == old:
                linenr = line.old_offset
                if linenr == first_context_line and line.type == diff.Line.INSERTED:
                    return False
            else:
                linenr = line.new_offset
                if linenr == first_context_line and line.type == diff.Line.DELETED:
                    return False

            return first_context_line <= linenr <= last_context_line

        file.loadOldLines(True)
        file.loadNewLines(True)

        context = diff.context.ContextLines(file, file.chunks, [chain])
        file.macro_chunks = context.getMacroChunks(context_lines, highlight=True, lineFilter=lineFilter)

        try: macro_chunk = file.macro_chunks[0]
        except: raise repr((parent.sha1, child.sha1))

        display_type = "both"

        if chain.state != "addressed":
            first_line_type = macro_chunk.lines[0].type
            if first_line_type == diff.Line.CONTEXT or (use == old and first_line_type == diff.Line.DELETED) or (use == new and first_line_type == diff.Line.INSERTED):
                for line in macro_chunk.lines[1:]:
                    if first_line_type != line.type:
                        break
                else:
                    display_type = "old" if use == old else "new"

        commit_url_component = "from=%s&to=%s" % (parent.sha1, child.sha1)

    def renderHeaderLeft(db, target, file):
        target.span("comment-chain-title").a(href="/showcomment?chain=%d" % chain.id).text(chain.title())

    def renderHeaderRight(db, target, file):
        side = use == old and "o" or "n"
        uri = "showcommit?%s&review=%d&file=%d#f%d%s%d" % (commit_url_component, review.id, file.id, file.id, side, first_line)
        target.span("filename").a(href=uri).text(file.path)

    def renderCommentsLocal(db, target, **kwargs):
        if display_type == "both":
            if use == old: position = "left"
            else: position = "right"
        else:
            position = "center"

        renderComments(db, target, user, chain, position, linkify)

    def lineId(base):
        return "c%d%s" % (chain.id, base)

    def lineCellId(base):
        return "c%d%s" % (chain.id, base)

    target.addInternalScript("commentChainById[%d] = %s;" % (chain.id, chain.getJSConstructor(sha1)), here=True)

    changeset_html.renderFile(db, target, user, review, file, options={ "support_expand": False, "display_type": display_type, "header_left": renderHeaderLeft, "header_right": renderHeaderRight, "content_after": renderCommentsLocal, "show": True, "expand": True, "line_id": lineId, "line_cell_id": lineCellId, "compact": compact, "tabify": tabify, "include_deleted": True })

    data = (chain.id, file_id, use == old and "o" or "n", first_line,
            chain.id, file_id, use == old and "o" or "n", last_line,
            htmlutils.jsify(chain.type), htmlutils.jsify(chain.state),
            chain.id)

    target.addInternalScript("""$(document).ready(function ()
  {
    var markers = new CommentMarkers(null);
    markers.setLines(document.getElementById('c%df%d%s%d'), document.getElementById('c%df%d%s%d'));
    markers.setType(%s, %s);
    commentChainById[%d].markers = markers;
  });""" % data, here=True)

def renderReviewCommentChain(db, target, user, review, chain, linkify=False, message=None):
    target.addInternalScript("commentChainById[%d] = %s;" % (chain.id, chain.getJSConstructor()), here=True)

    table = target.table("file show expanded first", width="60%", align="center", cellspacing=0, cellpadding=0)

    columns = table.colgroup()
    columns.col("edge").empty()
    columns.col("linenr").empty()
    columns.col("line").empty()
    columns.col("middle").empty()
    columns.col("middle").empty()
    columns.col("line").empty()
    columns.col("linenr").empty()
    columns.col("edge").empty()

    table.thead().tr().td("left", colspan=8, align="left").span("comment-chain-title").a(href="/showcomment?chain=%d" % chain.id).text(chain.title())
    table.tbody('spacer').tr('spacer').td(colspan='8').text()

    if message:
        row = table.tbody("content").tr("content")
        row.td(colspan=2).text()
        row.td("excuse", colspan=4).innerHTML(message)
        row.td(colspan=2).text()

    table.tbody('spacer').tr('spacer').td(colspan='8').text()

    row = table.tbody("content").tr("content")
    row.td(colspan=2).text()
    renderComments(db, row.td(colspan=4), user, chain, "center", linkify)
    row.td(colspan=2).text()

    table.tbody('spacer').tr('spacer').td(colspan='8').text()
    table.tfoot().tr().td("left", colspan=8, align="left").text()

def renderCommitCommentChain(db, target, user, review, chain, linkify=False):
    target.addInternalScript("commentChainById[%d] = %s;" % (chain.id, chain.getJSConstructor()), here=True)

    table = target.table("file show expanded first", width="60%", align="center", cellspacing=0, cellpadding=0)

    columns = table.colgroup()
    columns.col("edge").empty()
    columns.col("linenr").empty()
    columns.col("line").empty()
    columns.col("middle").empty()
    columns.col("middle").empty()
    columns.col("line").empty()
    columns.col("linenr").empty()
    columns.col("edge").empty()

    table.thead().tr().td("left", colspan=8, align="left").span("comment-chain-title").a(href="/showcomment?chain=%d" % chain.id).text(chain.title())
    table.tbody('spacer').tr('spacer').td(colspan='8').text()

    row = table.tbody("content").tr("content")
    row.td(colspan=2).text()
    page.showcommit.renderCommitInfo(db, row.td("content", colspan=4), user, review.repository, review, chain.first_commit, minimal=True)
    row.td(colspan=2).text()

    table.tbody('spacer').tr('spacer').td(colspan='8').text()

    row = table.tbody("content").tr("content")
    row.td(colspan=2).text()
    renderComments(db, row.td(colspan=4), user, chain, "center", linkify)
    row.td(colspan=2).text()

    table.tbody('spacer').tr('spacer').td(colspan='8').text()
    table.tfoot().tr().td("left", colspan=8, align="left").text()

def renderCommentChain(db, target, user, review, chain, context_lines=3, compact=False, tabify=False, original=False, changeset=None, linkify=False):
    chain.loadComments(db, user)

    target.addExternalStylesheet("resource/changeset.css")
    target.addExternalStylesheet("resource/comment.css")
    target.addExternalStylesheet("resource/review.css")
    target.addExternalScript("resource/changeset.js")
    target.addExternalScript("resource/comment.js")
    target.addExternalScript("resource/review.js")

    target = target.div("comment-chain", id="c%d" % chain.id)

    if chain.file_id:
        try: renderCodeCommentChain(db, target, user, review, chain, context_lines, compact, tabify, original, changeset, linkify)
        except:
            cursor = db.cursor()
            cursor.execute("SELECT first_line, last_line, commit FROM commentchainlines WHERE chain=%s ORDER BY time ASC LIMIT 1", (chain.id,))
            path = dbutils.describe_file(db, chain.file_id)
            first_line, last_line, commit_id = cursor.fetchone()
            commit = gitutils.Commit.fromId(db, review.repository, commit_id)

            if first_line == last_line: line = "line %d" % first_line
            else: line = "lines %d-%d" % (first_line, last_line)

            message = "<p><b>I'm terribly sorry, but this comment is broken in the database!</b></p><p>It was originally made against %s in some version of <code>%s</code>, in the commit <a href='%s/%s?review=%d&file=%d'>%s</a>.</p>" % (line, path, review.repository.name, commit.sha1, review.id, chain.file_id, commit.sha1)

            renderReviewCommentChain(db, target, user, review, chain, linkify, message)
    elif chain.first_commit:
        renderCommitCommentChain(db, target, user, review, chain, linkify)
    else:
        renderReviewCommentChain(db, target, user, review, chain, linkify)
