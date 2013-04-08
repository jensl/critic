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

import itertools
import re

import dbutils
import gitutils
import reviewing.utils
import log.html
import htmlutils
import page.utils
import diff
import configuration
import linkify

from textutils import json_decode, json_encode

def generateReviewersAndWatchersTable(db, repository, target, all_reviewers, all_watchers, applyfilters=True, applyparentfilters=False):
    cursor = db.cursor()
    teams = reviewing.utils.collectReviewTeams(all_reviewers)

    reviewers = set()
    watchers = set()

    for file_id, file_reviewers in all_reviewers.items():
        for user_id in file_reviewers:
            reviewers.add(user_id)

    for file_id, file_watchers in all_watchers.items():
        for user_id in file_watchers:
            if user_id not in reviewers:
                watchers.add(user_id)

    table = target.table("filters paleyellow", align="center")
    table.tr().td("h1", colspan=3).h1().text("Reviewers and Watchers")

    row = table.tr("applyfilters")
    row.td("value").input("applyfilters", type="checkbox", checked=("checked" if applyfilters else None))
    row.td("legend", colspan=2).text("Apply global filters. Only disable this in inofficial reviews!")

    table.tr("watchers").td("spacer", colspan=3)

    if repository.parent and applyfilters:
        parent = repository.parent
        parents = []

        while parent:
            parents.append(parent.name)
            parent = parent.parent

        if len(parents) == 1: parents = "repository (%s)" % parents[0]
        else: parents = "repositories (%s)" % ", ".join(parents)

        row = table.tr("applyfilters")
        row.td("value").input("applyparentfilters", type="checkbox", checked=("checked" if applyparentfilters else None))
        row.td("legend", colspan=2).text("Apply global filters from upstream %s." % parents)

        table.tr("watchers").td("spacer", colspan=3)

    def formatFiles(files):
        return diff.File.eliminateCommonPrefixes(sorted([dbutils.describe_file(db, file_id) for file_id in files]))

    for team in teams:
        if team is not None:
            row = table.tr("reviewers")

            cell = row.td("reviewers")
            users = sorted([dbutils.User.fromId(db, user_id).fullname for user_id in team])
            for user in users: cell.text(user).br()
            row.td("willreview").innerHTML("will&nbsp;review")

            cell = row.td("files")
            for file in formatFiles(teams[team]):
                cell.span("file").innerHTML(file).br()

    if None in teams:
        row = table.tr("reviewers")
        row.td("no-one", colspan=2).text("No reviewers found for changes in")

        cell = row.td("files")
        for file in formatFiles(teams[None]):
            cell.span("file").innerHTML(file).br()

    if watchers:
        table.tr("watchers").td("spacer", colspan=3)

        row = table.tr("watchers")
        row.td("heading", colspan=2).text("Watchers")
        cell = row.td("watchers")
        for user_id in watchers: cell.text(dbutils.User.fromId(db, user_id).fullname).br()

    table.tr("buttons").td("spacer", colspan=3)

    buttons = table.tr("buttons").td("buttons", colspan=3)
    buttons.button(onclick="addReviewer();").text("Add Reviewer")
    buttons.button(onclick="addWatcher();").text("Add Watcher")

def renderSelectSource(req, db, user):
    cursor = db.cursor()

    document = htmlutils.Document(req)
    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, current_page="createreview")

    document.addExternalStylesheet("resource/createreview.css")
    document.addExternalScript("resource/createreview.js")
    document.addExternalScript("resource/autocomplete.js")

    document.addInternalScript(user.getJS(db))
    document.setTitle("Create Review")

    target = body.div("main")
    table = page.utils.PaleYellowTable(target, "Create Review")
    table.titleRight.innerHTML("Step 1")

    default_repository = user.getPreference(db, "defaultRepository")
    default_remotes = {}
    default_branches = {}

    def renderLocalRepository(target):
        repositories = target.select("repository")

        cursor.execute("""SELECT repositories.id, repositories.name, repositories.path, branches.name
                            FROM repositories
                 LEFT OUTER JOIN branches ON (branches.id=repositories.branch)
                        ORDER BY id""")

        for repository_id, name, path, branch_name in cursor.fetchall():
            option = repositories.option("repository", value=name, selected="selected" if name == default_repository else None)
            option.text("%s [%s:%s]" % (name, configuration.base.HOSTNAME, path))

            local_names = ["*"]

            if branch_name:
                local_names.append(branch_name)

            cursor.execute("""SELECT remote
                                FROM trackedbranches
                               WHERE repository=%s
                                 AND local_name=ANY (%s)
                            ORDER BY local_name
                               LIMIT 1""",
                           (repository_id, local_names))

            def splitRemote(remote):
                if remote.startswith("git://"):
                    host, path = remote[6:].split("/", 1)
                    host = "git://" + host
                else:
                    host, path = remote.split(":", 1)
                return host, path

            row = cursor.fetchone()

            if row: default_remotes[name] = splitRemote(row[0])
            else: default_remotes[name] = None

            default_branches[name] = branch_name

        document.addInternalScript("var default_remotes = %s;" % json_encode(default_remotes))
        document.addInternalScript("var default_branches = %s;" % json_encode(default_branches))

    def renderRemoteRepository(target):
        host = target.p("remotehost")
        host.text("Host: ")
        hosts = host.select("remotehost")

        cursor.execute("SELECT name, path FROM knownhosts ORDER BY id")

        default_remote = default_remotes.get(default_repository)

        for name, path in cursor:
            option = hosts.option("remotehost", value=name, critic_default_path=path,
                                  selected="selected" if default_remote and default_remote[0] == name else None)
            option.text(name)

        path = target.p("remotepath")
        path.text("Path: ")
        path.input("remotepath", value=default_remote[1] if default_remote else None)

    def renderWorkBranch(target):
        target.text("refs/heads/")
        target.input("workbranch")

    def renderUpstreamCommit(target):
        default_branch = default_branches.get(default_repository)
        target.input("upstreamcommit", value=("refs/heads/%s" % default_branch) if default_branch else "")

    table.addItem("Local Repository", renderLocalRepository, "Critic repository to create review in.")
    table.addItem("Remote Repository", renderRemoteRepository, "Remote repository to fetch commits from.")
    table.addItem("Work Branch", renderWorkBranch, "Work branch (in remote repository) containing commits to create review of.")
    table.addItem("Upstream Commit", renderUpstreamCommit, "Upstream commit from which the work branch was branched.")

    def renderButtons(target):
        target.button("fetchbranch").text("Fetch Branch")

    table.addCentered(renderButtons)

    return document

def renderCreateReview(req, db, user):
    if user.isAnonymous(): raise page.utils.NeedLogin, req

    repository = req.getParameter("repository", filter=gitutils.Repository.FromParameter(db), default=None)
    applyparentfilters = req.getParameter("applyparentfilters", "yes" if user.getPreference(db, 'review.applyUpstreamFilters') else "no") == "yes"

    cursor = db.cursor()

    if req.method == "POST":
        data = json_decode(req.read())

        summary = data.get("summary")
        description = data.get("description")
        review_branch_name = data.get("review_branch_name")
        commit_ids = data.get("commit_ids")
        commit_sha1s = data.get("commit_sha1s")
    else:
        summary = req.getParameter("summary", None)
        description = req.getParameter("description", None)
        review_branch_name = req.getParameter("reviewbranchname", None)

        commit_ids = None
        commit_sha1s = None

        commits_arg = req.getParameter("commits", None)
        remote = req.getParameter("remote", None)
        upstream = req.getParameter("upstream", "master")
        branch_name = req.getParameter("branch", None)

        if commits_arg:
            try: commit_ids = map(int, commits_arg.split(","))
            except: commit_sha1s = [repository.revparse(ref) for ref in commits_arg.split(",")]
        elif branch_name:
            cursor.execute("""SELECT commit
                                FROM reachable
                                JOIN branches ON (branch=id)
                               WHERE repository=%s
                                 AND name=%s""",
                           (repository.id, branch_name))
            commit_ids = [commit_id for (commit_id,) in cursor]

            if len(commit_ids) > configuration.limits.MAXIMUM_REVIEW_COMMITS:
                raise page.utils.DisplayMessage(
                    "Too many commits!",
                    (("<p>The branch <code>%s</code> contains %d commits.  Reviews can"
                      "be created from branches that contain at most %d commits.</p>"
                      "<p>This limit can be adjusted by modifying the system setting"
                      "<code>configuration.limits.MAXIMUM_REVIEW_COMMITS</code>.</p>")
                     % (htmlutils.htmlify(branch_name), len(commit_ids),
                        configuration.limits.MAXIMUM_REVIEW_COMMITS)),
                    html=True)
        else:
            return renderSelectSource(req, db, user)

    req.content_type = "text/html; charset=utf-8"

    if commit_ids:
        commits = [gitutils.Commit.fromId(db, repository, commit_id) for commit_id in commit_ids]
    elif commit_sha1s:
        commits = [gitutils.Commit.fromSHA1(db, repository, commit_sha1) for commit_sha1 in commit_sha1s]
    else:
        commits = []

    if not commit_ids:
        commit_ids = [commit.getId(db) for commit in commits]
    if not commit_sha1s:
        commit_sha1s = [commit.sha1 for commit in commits]

    if summary is None:
        if len(commits) == 1:
            summary = commits[0].summary()
        else:
            summary = ""

    if review_branch_name:
        invalid_branch_name = "false"
        default_branch_name = review_branch_name
    else:
        invalid_branch_name = htmlutils.jsify(user.name + "/")
        default_branch_name = user.name + "/"

        match = re.search("(?:^|[Ff]ix(?:e[ds])?(?: +for)?(?: +bug)? +)([A-Z][A-Z0-9]+-[0-9]+)", summary)
        if match:
            invalid_branch_name = "false"
            default_branch_name = htmlutils.htmlify(match.group(1))

    all_reviewers, all_watchers = reviewing.utils.getReviewersAndWatchers(db, repository, commits, applyparentfilters=applyparentfilters)

    document = htmlutils.Document(req)
    html = document.html()
    head = html.head()

    document.addInternalScript(user.getJS(db))

    if branch_name:
        document.addInternalScript("var fromBranch = %s;" % htmlutils.jsify(branch_name))

    if remote:
        document.addInternalScript("var trackedbranch = { remote: %s, name: %s };" % (htmlutils.jsify(remote), htmlutils.jsify(branch_name)))

    cursor.execute("SELECT name, fullname FROM users WHERE name IS NOT NULL AND status!='retired'")

    users = []

    for name, fullname in cursor:
        users.append("%s:%s" % (htmlutils.jsify(name), htmlutils.jsify(fullname)))

    head.title().text("Create Review")

    body = html.body(onload="document.getElementById('branch_name').focus()")

    page.utils.generateHeader(body, db, user, lambda target: target.button(onclick="submitReview();").text("Submit Review"))

    document.addExternalStylesheet("resource/createreview.css")
    document.addExternalScript("resource/createreview.js")
    document.addExternalScript("resource/autocomplete.js")

    document.addInternalScript("var users = {%s};" % ",".join(users))
    document.addInternalScript("""
var invalid_branch_name = %s;
var review = { commit_ids: %r,
               commit_sha1s: %r };""" % (invalid_branch_name, commit_ids, commit_sha1s))
    document.addInternalScript(repository.getJS())

    main = body.div("main")

    table = main.table("basic paleyellow", align="center")
    table.tr().td("h1", colspan=3).h1().text("Create Review")

    row = table.tr("line")
    row.td("heading").text("Branch Name:")
    row.td("value").text("r/").input("value", id="branch_name", size=80, value=default_branch_name)
    row.td("status")

    row = table.tr()

    if not remote:
        row.td("help", colspan=3).div().text("""\
This is the main identifier of the review.  It will be created in the review
repository to contain the commits below.  Reviewers can fetch it from there, and
additional commits can be added to the review later by pushing them to this
branch in the review repository.""")
    else:
        row.td("help", colspan=3).div().text("""\
This is the main identifier of the review.  It will be created in the review
repository to contain the commits below, and reviewers can fetch it from there.""")

    if remote:
        row = table.tr("line")
        row.td("heading").text("Tracked Branch:")
        value = row.td("value")
        value.code("branch").text(branch_name, linkify=linkify.Context(remote=remote))
        value.text(" in ")
        value.code("remote").text(remote, linkify=linkify.Context())
        row.td("status")

        row = table.tr()
        row.td("help", colspan=3).div().text("""\
Rather than pushing directly to the review branch in Critic's repository to add
commits to the review, you will be pushing to this branch (in a separate
repository,) from which Critic will fetch commits and add them to the review
automatically.""")

    row = table.tr("line")
    row.td("heading").text("Summary:")
    row.td("value").input("value", id="summary", size=80, value=summary)
    row.td("status")

    row = table.tr()
    row.td("help", colspan=3).div().text("""\
The summary should be a short summary of the changes in the review.  It will
appear in the subject of all emails sent about the review.
""")

    row = table.tr("line")
    row.td("heading").text("Description:")
    textarea = row.td("value").textarea(id="description", cols=80, rows=12)
    textarea.preformatted()
    if description: textarea.text(description)
    row.td("status")

    row = table.tr()
    row.td("help", colspan=3).div().text("""\
The description should describe the changes to be reviewed.  It is usually fine
to leave the description empty, since the commit messages are also available in
the review.
""")

    generateReviewersAndWatchersTable(db, repository, main, all_reviewers, all_watchers, applyparentfilters=applyparentfilters)

    row = table.tr("line")
    row.td("heading").text("Recipient List:")
    cell = row.td("value", colspan=2).preformatted()
    cell.span("mode").text("Everyone")
    cell.span("users")
    cell.text(".")
    buttons = cell.div("buttons")
    buttons.button(onclick="editRecipientList();").text("Edit Recipient List")

    row = table.tr()
    row.td("help", colspan=3).div().text("""\
The basic recipient list for e-mails sent about the review.
""")

    log.html.render(db, main, "Commits", commits=commits)

    return document
