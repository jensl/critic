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
import log.html
import log.commitset

def renderConfirmMerge(req, db, user):
    confirmation_id = req.getParameter("id", filter=int)
    tail_sha1 = req.getParameter("tail", None)
    do_confirm = req.getParameter("confirm", "no") == "yes"
    do_cancel = req.getParameter("cancel", "no") == "yes"

    cursor = db.cursor()

    cursor.execute("SELECT review, uid, merge, confirmed, tail FROM reviewmergeconfirmations WHERE id=%s", (confirmation_id,))
    row = cursor.fetchone()
    if not row:
        raise page.utils.DisplayMessage("No pending merge with that id.")
    review_id, user_id, merge_id, confirmed, tail_id = row

    review = dbutils.Review.fromId(db, review_id)
    merge = gitutils.Commit.fromId(db, review.repository, merge_id)

    if confirmed and tail_id is not None:
        tail_sha1 = gitutils.Commit.fromId(db, review.repository, tail_id).sha1

    cursor.execute("SELECT merged FROM reviewmergecontributions WHERE id=%s", (confirmation_id,))

    merged = [gitutils.Commit.fromId(db, review.repository, merged_id) for (merged_id,) in cursor]
    merged_set = log.commitset.CommitSet(merged)

    if tail_sha1 is not None:
        tail = gitutils.Commit.fromSHA1(db, review.repository, tail_sha1)
        tail_id = tail.getId(db)

        cut = [gitutils.Commit.fromSHA1(db, review.repository, sha1)
               for sha1 in tail.parents if sha1 in merged_set]
        merged_set = merged_set.without(cut)
        merged = list(merged_set)
    else:
        tail_id = None

    if do_confirm:
        cursor.execute("UPDATE reviewmergeconfirmations SET confirmed=TRUE, tail=%s WHERE id=%s", (tail_id, confirmation_id))
        db.commit()
    elif do_cancel:
        cursor.execute("DELETE FROM reviewmergeconfirmations WHERE id=%s", (confirmation_id,))
        db.commit()

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    def renderButtons(target):
        if not do_confirm and not do_cancel:
            target.button("confirmAll").text("Confirm (merge + contributed)")
            target.button("confirmNone").text("Confirm (merge only)")
            target.button("cancel").text("Cancel")

    page.utils.generateHeader(body, db, user, renderButtons, extra_links=[("r/%d" % review.id, "Back to Review")])

    document.addExternalStylesheet("resource/confirmmerge.css")
    document.addExternalScript("resource/log.js")
    document.addExternalScript("resource/confirmmerge.js")
    document.addInternalScript(user.getJS())
    document.addInternalScript(review.getJS())
    document.addInternalScript("var confirmation_id = %d;" % confirmation_id)
    document.addInternalScript("var merge_sha1 = %s;" % htmlutils.jsify(merge.sha1))

    if tail_sha1 is not None:
        document.addInternalScript("var tail_sha1 = %s;" % htmlutils.jsify(tail_sha1))

    if not do_confirm and not do_cancel:
        heads = merged_set.getHeads()
        if heads:
            document.addInternalScript("var automaticAnchorCommit = %s;" % htmlutils.jsify(heads.pop().sha1))
        else:
            document.addInternalScript("var automaticAnchorCommit = null;")

    if do_confirm:
        document.addInternalScript("var confirmed = true;")
    else:
        document.addInternalScript("var confirmed = false;")

    target = body.div("main")

    basic = target.table('confirm', align='center')
    basic.col(width='10%')
    basic.col(width='60%')
    basic.col(width='30%')
    h1 = basic.tr().td('h1', colspan=3).h1()

    if do_confirm:
        h1.text("CONFIRMED MERGE")
    elif do_cancel:
        h1.text("CANCELLED MERGE")
    else:
        h1.text("Confirm Merge")

    row = basic.tr("sha1")
    row.td("heading").text("SHA-1:")
    row.td("value").preformatted().text(merge.sha1)
    row.td().text()

    row = basic.tr("message")
    row.td("heading").text("Message:")
    row.td("value").preformatted().text(merge.message)
    row.td().text()

    if merged:
        columns = [(10, log.html.WhenColumn()),
                   (60, log.html.SummaryColumn()),
                   (16, log.html.AuthorColumn())]

        log.html.render(db, target, "Contributed Commits", commits=merged, columns=columns)

    return document
