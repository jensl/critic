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
import page.utils
import profiling
import linkify

import reviewing.comment as review_comment
import reviewing.utils as review_utils
import reviewing.html as review_html
import changeset.utils as changeset_utils

import operation.blame
import log.commitset

def renderShowComment(req, db, user):
    chain_id = req.getParameter("chain", filter=int)
    context_lines = req.getParameter("context", user.getPreference(db, "comment.diff.contextLines"), filter=int)

    default_compact = "yes" if user.getPreference(db, "commit.diff.compactMode") else "no"
    compact = req.getParameter("compact", default_compact) == "yes"

    default_tabify = "yes" if user.getPreference(db, "commit.diff.visualTabs") else "no"
    tabify = req.getParameter("tabify", default_tabify) == "yes"

    original = req.getParameter("original", "no") == "yes"

    chain = review_comment.CommentChain.fromId(db, chain_id, user)

    if chain is None or chain.state == "empty":
        raise page.utils.DisplayMessage, "Invalid comment chain ID: %d" % chain_id

    review = chain.review

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    document.setTitle("%s in review %s" % (chain.title(False), review.branch.name))

    def renderHeaderItems(target):
        review_utils.renderDraftItems(db, user, review, target)
        target.div("buttons").span("buttonscope buttonscope-global")

    page.utils.generateHeader(body, db, user, renderHeaderItems, extra_links=[("r/%d" % review.id, "Back to Review")])

    document.addExternalScript("resource/showcomment.js")
    document.addInternalScript(user.getJS(db))
    document.addInternalScript(review.repository.getJS())
    document.addInternalScript(review.getJS())
    document.addInternalScript("var contextLines = %d;" % context_lines)
    document.addInternalScript("var keyboardShortcuts = %s;" % (user.getPreference(db, "ui.keyboardShortcuts") and "true" or "false"))

    if not user.isAnonymous() and user.name == req.user:
        document.addInternalScript("$(function () { markChainsAsRead([%d]); });" % chain_id)

    review_html.renderCommentChain(db, body.div("main"), user, review, chain, context_lines=context_lines, compact=compact, tabify=tabify, original=original, linkify=linkify.Context(db=db, request=req, review=review))

    if user.getPreference(db, "ui.keyboardShortcuts"):
        page.utils.renderShortcuts(body, "showcomment")

    yield document.render(pretty=not compact)

def renderShowComments(req, db, user):
    context_lines = req.getParameter("context", user.getPreference(db, "comment.diff.contextLines"), filter=int)

    default_compact = "yes" if user.getPreference(db, "commit.diff.compactMode") else "no"
    compact = req.getParameter("compact", default_compact) == "yes"

    default_tabify = "yes" if user.getPreference(db, "commit.diff.visualTabs") else "no"
    tabify = req.getParameter("tabify", default_tabify) == "yes"

    original = req.getParameter("original", "no") == "yes"

    review_id = req.getParameter("review", filter=int)
    batch_id = req.getParameter("batch", None, filter=int)
    filter = req.getParameter("filter", "all")
    blame = req.getParameter("blame", None)

    profiler = profiling.Profiler()

    review = dbutils.Review.fromId(db, review_id)
    review.repository.enableBlobCache()

    cursor = db.cursor()

    profiler.check("create review")

    if blame is not None:
        blame_user = dbutils.User.fromName(db, blame)

        cursor.execute("""SELECT commentchains.id
                            FROM commentchains
                            JOIN commentchainlines ON (commentchainlines.chain=commentchains.id)
                            JOIN fileversions ON (fileversions.new_sha1=commentchainlines.sha1)
                            JOIN changesets ON (changesets.id=fileversions.changeset)
                            JOIN commits ON (commits.id=changesets.child)
                            JOIN gitusers ON (gitusers.id=commits.author_gituser)
                            JOIN usergitemails USING (email)
                            JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id AND reviewchangesets.review=commentchains.review)
                           WHERE commentchains.review=%s
                             AND usergitemails.uid=%s
                             AND commentchains.state!='empty'
                             AND (commentchains.state!='draft' OR commentchains.uid=%s)
                        ORDER BY commentchains.file, commentchainlines.first_line""",
                       (review.id, blame_user.id, user.id))

        include_chain_ids = set([chain_id for (chain_id,) in cursor])

        profiler.check("initial blame filtering")
    else:
        include_chain_ids = None

    if filter == "toread":
        query = """SELECT commentchains.id
                     FROM commentchains
                     JOIN comments ON (comments.chain=commentchains.id)
                     JOIN commentstoread ON (commentstoread.comment=comments.id)
          LEFT OUTER JOIN commentchainlines ON (commentchainlines.chain=commentchains.id)
                    WHERE review=%s
                      AND commentstoread.uid=%s
                 ORDER BY file, first_line"""

        cursor.execute(query, (review.id, user.id))
    else:
        query = """SELECT commentchains.id
                     FROM commentchains
          LEFT OUTER JOIN commentchainlines ON (chain=id)
                    WHERE review=%s
                      AND commentchains.state!='empty'"""

        arguments = [review.id]

        if filter == "issues":
            query += " AND type='issue' AND (commentchains.state!='draft' OR commentchains.uid=%s)"
            arguments.append(user.id)
        elif filter == "draft-issues":
            query += " AND type='issue' AND commentchains.state='draft' AND commentchains.uid=%s"
            arguments.append(user.id)
        elif filter == "open-issues":
            query += " AND type='issue' AND commentchains.state='open'"
        elif filter == "addressed-issues":
            query += " AND type='issue' AND commentchains.state='addressed'"
        elif filter == "closed-issues":
            query += " AND type='issue' AND commentchains.state='closed'"
        elif filter == "notes":
            query += " AND type='note' AND (commentchains.state!='draft' OR commentchains.uid=%s)"
            arguments.append(user.id)
        elif filter == "draft-notes":
            query += " AND type='note' AND commentchains.state='draft' AND commentchains.uid=%s"
            arguments.append(user.id)
        elif filter == "open-notes":
            query += " AND type='note' AND commentchains.state='open'"
        else:
            query += " AND (commentchains.state!='draft' OR commentchains.uid=%s)"
            arguments.append(user.id)

        if batch_id is not None:
            query += " AND batch=%s"
            arguments.append(batch_id)

        # This ordering is inaccurate if comments apply to the same file but
        # different commits, but then, in that case there isn't really a
        # well-defined natural order either.  Two comments that apply to the
        # same file and commit will at least be order by line number, and that's
        # better than nothing.
        query += " ORDER BY file, first_line"

        cursor.execute(query, arguments)

    profiler.check("main query")

    if include_chain_ids is None:
        chain_ids = [chain_id for (chain_id,) in cursor]
    else:
        chain_ids = [chain_id for (chain_id,) in cursor if chain_id in include_chain_ids]

    profiler.check("query result")

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    document.addInternalScript(user.getJS(db))
    document.addInternalScript(review.getJS())

    page.utils.generateHeader(body, db, user, lambda target: review_utils.renderDraftItems(db, user, review, target), extra_links=[("r/%d" % review.id, "Back to Review")])

    profiler.check("page header")

    target = body.div("main")

    if chain_ids and not user.isAnonymous() and user.name == req.user:
        document.addInternalScript("$(function () { markChainsAsRead([%s]); });" % ", ".join(map(str, chain_ids)))

    if chain_ids:
        processed = set()

        chains = []
        file_ids = set()
        changesets_files = {}
        changesets = {}

        if blame is not None:
            annotators = {}
            review.branch.loadCommits(db)
            commits = log.commitset.CommitSet(review.branch.commits)

        for chain_id in chain_ids:
            if chain_id in processed:
                continue
            else:
                processed.add(chain_id)

                chain = review_comment.CommentChain.fromId(db, chain_id, user, review=review)
                chains.append(chain)

                if chain.file_id is not None:
                    file_ids.add(chain.file_id)
                    parent, child = review_html.getCodeCommentChainChangeset(db, chain, original)
                    if parent and child:
                        changesets_files.setdefault((parent, child), set()).add(chain.file_id)

        profiler.check("load chains")

        changeset_cache = {}

        for (from_commit, to_commit), filtered_file_ids in changesets_files.items():
            changesets[(from_commit, to_commit)] = changeset_utils.createChangeset(db, user, review.repository, from_commit=from_commit, to_commit=to_commit, filtered_file_ids=filtered_file_ids)[0]
            profiler.check("create changesets")

            if blame is not None:
                annotators[(from_commit, to_commit)] = operation.blame.LineAnnotator(db, from_commit, to_commit, file_ids=file_ids, commits=commits, changeset_cache=changeset_cache)
                profiler.check("create annotators")

        for chain in chains:
            if blame is not None and chain.file_id is not None:
                try:
                    changeset = changesets[(chain.first_commit, chain.last_commit)]
                    annotator = annotators[(chain.first_commit, chain.last_commit)]
                except KeyError:
                    # Most likely a comment created via /showfile.  Such a
                    # comment could be in code that 'blame_user' modified in the
                    # review, but for now, let's skip the comment.
                    continue
                else:
                    file_in_changeset = changeset.getFile(chain.file_id)

                    if not file_in_changeset:
                        continue

                    try:
                        offset, count = chain.lines_by_sha1[file_in_changeset.new_sha1]
                    except KeyError:
                        # Probably a chain raised against the "old" side of the diff.
                        continue
                    else:
                        if not annotator.annotate(chain.file_id, offset, offset + count - 1, check_user=blame_user):
                            continue

            profiler.check("detailed blame filtering")

            if chain.file_id is not None:
                from_commit, to_commit = review_html.getCodeCommentChainChangeset(db, chain, original)
                changeset = changesets.get((from_commit, to_commit))
            else:
                changeset = None

            review_html.renderCommentChain(db, target, user, review, chain,
                                           context_lines=context_lines,
                                           compact=compact,
                                           tabify=tabify,
                                           original=original,
                                           changeset=changeset,
                                           linkify=linkify.Context(db=db, request=req, review=review))

            profiler.check("rendering")

            yield document.render(stop=target, pretty=not compact) + "<script>console.log((new Date).toString());</script>"

            profiler.check("transfer")

        page.utils.renderShortcuts(target, "showcomments")
    else:
        target.h1(align="center").text("No comments.")

    profiler.output(db, user, document)

    yield document.render(pretty=not compact)
