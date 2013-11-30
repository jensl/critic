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
import htmlutils
import dbutils
import gitutils
import configuration

def renderRepositories(req, db, user):
    req.content_type = "text/html; charset=utf-8"

    document = htmlutils.Document(req)
    document.setTitle("Repositories")

    html = document.html()
    head = html.head()
    body = html.body()

    def generateRight(target):
        if user.hasRole(db, "repositories"):
            target.a("button", href="newrepository").text("Add Repository")

    page.utils.generateHeader(body, db, user, current_page="repositories", generate_right=generateRight)

    document.addExternalStylesheet("resource/repositories.css")
    document.addExternalScript("resource/repositories.js")
    document.addInternalScript(user.getJS())

    if user.name == req.user and user.hasRole(db, "administrator"):
        document.addInternalScript("user.administrator = true;")

    cursor = db.cursor()
    cursor.execute("SELECT id, name, path, parent, branch FROM repositories ORDER BY name ASC")

    rows = cursor.fetchall()

    class Repository:
        def __init__(self, repository_id, name, path, parent_id, branch_id):
            self.id = repository_id
            self.name = name
            self.path = path
            self.parent_id = parent_id
            self.branch_id = branch_id
            self.default_remote = None
            self.location = gitutils.Repository.constructURL(db, user, path)

    repositories = list(Repository(*row) for row in rows)
    repository_by_id = dict((repository.id, repository) for repository in repositories)

    def render(target):
        table = target.table("repositories callout", cellspacing=0, align="center")

        headings = table.tr("headings")
        headings.th("name").text("Short name")
        headings.th("location").text("Location")
        headings.th("upstream").text("Upstream")

        table.tr("spacer").td("spacer", colspan=3)

        for repository in repositories:
            row = table.tr("repository %s" % repository.name)
            row.td("name").text(repository.name)
            row.td("location").text(repository.location)

            if repository.parent_id:
                row.td("upstream").text(repository_by_id[repository.parent_id].name)
            else:
                row.td("upstream").text()

            cursor.execute("""SELECT id, local_name, remote, remote_name, disabled
                                FROM trackedbranches
                               WHERE repository=%s
                            ORDER BY id ASC""",
                           (repository.id,))

            details = table.tr("details %s" % repository.name).td(colspan=3)

            branches = [(branch_id, local_name, remote, remote_name, disabled)
                        for branch_id, local_name, remote, remote_name, disabled in cursor
                        if not local_name.startswith("r/")]

            if branches:
                trackedbranches = details.table("trackedbranches", cellspacing=0)
                trackedbranches.tr().th("title", colspan=5).text("Tracked Branches")

                row = trackedbranches.tr("headings")
                row.th("localname").text("Local branch")
                row.th("remote").text("Repository")
                row.th("remotename").text("Remote branch")
                row.th("enabled").text("Enabled")
                row.th("users").text("Users")

                default_remote = ""

                for branch_id, local_name, remote, remote_name, disabled in sorted(branches, key=lambda branch: branch[1]):
                    cursor.execute("SELECT uid FROM trackedbranchusers WHERE branch=%s", (branch_id,))

                    user_ids = [user_id for (user_id,) in cursor.fetchall()]

                    row = trackedbranches.tr("branch", critic_branch_id=branch_id, critic_user_ids=",".join(map(str, user_ids)))

                    if local_name == "*":
                        row.td("localname").i().text("Tags")
                        default_remote = remote
                    else:
                        row.td("localname").text(local_name)
                        if local_name == "master" and not default_remote:
                            default_remote = remote
                    row.td("remote").text(remote)
                    if remote_name == "*":
                        row.td("remotename").i().text("N/A")
                    else:
                        row.td("remotename").text(remote_name)
                    row.td("enabled").text("No" if disabled else "Yes")

                    cell = row.td("users")

                    for index, user_id in enumerate(user_ids):
                        if index: cell.text(", ")
                        trackedbranch_user = dbutils.User.fromId(db, user_id)
                        cell.span("user").text(trackedbranch_user.name)

                if default_remote:
                    repository.default_remote = default_remote

            buttons = details.div("buttons")
            buttons.button(onclick="addTrackedBranch(%d);" % repository.id).text("Add Tracked Branch")

    paleyellow = page.utils.PaleYellowTable(body, "Repositories")
    paleyellow.addCentered(render)

    repositories_js = []

    for repository in repositories:
        name = htmlutils.jsify(repository.name)
        path = htmlutils.jsify(repository.path)
        location = htmlutils.jsify(repository.location)
        default_remote = htmlutils.jsify(repository.default_remote)

        repositories_js.append(("%d: { name: %s, path: %s, location: %s, defaultRemoteLocation: %s }"
                                % (repository.id, name, path, location, default_remote)))

    document.addInternalScript("var repositories = { %s };" % ", ".join(repositories_js))

    return document
