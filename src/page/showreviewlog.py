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
import log.html
import reviewing.utils as review_utils
import reviewing.html as review_html
import reviewing.comment as review_comment
import re
import diff

re_module = re.compile("^((?:data|modules|platforms)/[^/]+)/.*$")

def renderShowReviewLog(req, db, user):
    review_id = page.utils.getParameter(req, "review", filter=int)
    granularity = page.utils.getParameter(req, "granularity")
    unassigned = page.utils.getParameter(req, "unassigned", "no") == "yes"

    cursor = db.cursor()

    review = dbutils.Review.fromId(db, review_id)

    document = htmlutils.Document(req)
    html = document.html()
    head = html.head()
    body = html.body()

    head.title("Review Log: %s" % review.branch.name)

    page.utils.generateHeader(body, db, user, lambda target: review_utils.renderDraftItems(db, user, review, target), extra_links=[("r/%d" % review.id, "Back to Review")])

    document.addExternalStylesheet("resource/showreviewlog.css")
    document.addExternalStylesheet("resource/review.css")
    document.addExternalScript("resource/review.js")
    document.addInternalScript(review.getJS())

    target = body.div("main")

    reviewed_reviewers = review_utils.getReviewedReviewers(db, review)

    def formatFiles(files):
        paths = sorted([dbutils.describe_file(db, file_id) for file_id in files])
        if granularity == "file":
            return diff.File.eliminateCommonPrefixes(paths)
        else:
            modules = set()
            files = []
            for path in paths:
                match = re_module.match(path)
                if match: modules.add(match.group(1))
                else: files.append(path)
            return sorted(modules) + diff.File.eliminateCommonPrefixes(files)

    if reviewed_reviewers and not unassigned:
        reviewed = target.table("paleyellow")
        reviewed.col(width="30%")
        reviewed.col(width="10%")
        reviewed.col(width="60%")
        reviewed.tr().td('h1', colspan=3).h1().text("Reviewed Changes")

        teams = review_utils.collectReviewTeams(reviewed_reviewers)

        for team in teams:
            row = reviewed.tr("reviewers")

            cell = row.td("reviewers")
            users = sorted([dbutils.User.fromId(db, user_id).fullname for user_id in team])
            for user in users: cell.text(user).br()
            row.td("willreview").innerHTML("reviewed")

            cell = row.td("files")
            for file in formatFiles(teams[team]):
                cell.span("file").innerHTML(file).br()

    pending_reviewers = review_utils.getPendingReviewers(db, review)

    if pending_reviewers:
        pending = target.table("paleyellow")
        pending.col(width="30%")
        pending.col(width="10%")
        pending.col(width="60%")
        pending.tr().td('h1', colspan=3).h1().text("Pending Changes")

        teams = review_utils.collectReviewTeams(pending_reviewers)

        if not unassigned:
            for team in teams:
                if team is not None:
                    row = pending.tr("reviewers")

                    cell = row.td("reviewers")
                    users = sorted([dbutils.User.fromId(db, user_id).fullname for user_id in team])
                    for user in users: cell.text(user).br()
                    row.td("willreview").innerHTML("should&nbsp;review")

                    cell = row.td("files")
                    for file in formatFiles(teams[team]):
                        cell.span("file").innerHTML(file).br()

        if None in teams:
            row = pending.tr("reviewers")
            row.td("no-one", colspan=2).text("No reviewers found for changes in")

            cell = row.td("files")
            for file in formatFiles(teams[None]):
                cell.span("file").innerHTML(file).br()

    return document
