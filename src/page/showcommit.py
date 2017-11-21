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
import page.utils
import dbutils
import gitutils
import diff
import changeset.html as changeset_html
import changeset.utils as changeset_utils
import changeset.detectmoves as changeset_detectmoves
import reviewing.utils as review_utils
import reviewing.comment as review_comment
import reviewing.filters as review_filters
import log.html as log_html
from log.commitset import CommitSet
import profiling
import re

def renderCommitInfo(db, target, user, repository, review, commit, conflicts=False, minimal=False):
    cursor = db.cursor()

    msg = commit.message.splitlines()

    commit_info = target.table("commit-info")

    def outputBranches(target, commit):
        cursor.execute("""SELECT branches.name, reviews.id
                            FROM branches
                            JOIN branchcommits ON (branchcommits.branch=branches.id)
                            JOIN commits ON (commits.id=branchcommits.commit)
                 LEFT OUTER JOIN reviews ON (reviews.branch=branches.id)
                           WHERE branches.repository=%s
                             AND commits.sha1=%s""",
                       (repository.id, commit.sha1))

        for branch, review_id in cursor:
            span = cell.span("branch")

            if review_id is None:
                url = htmlutils.URL("/log", repository=repository.id, branch=branch)
                title = branch
            else:
                url = "/r/%d" % review_id
                title = url

            span.text("[")
            span.a("branch", href=url).text(title)
            span.text("]")

    def outputTags(target, commit):
        cursor.execute("SELECT name FROM tags WHERE repository=%s AND sha1=%s",
                       (repository.id, commit.sha1))

        for (tag,) in cursor:
            target.span("tag").text("[%s]" % tag)

    if len(commit.parents) > 1:
        row = commit_info.tr("commit-info")
        row.th(align='right').text("Alternate view:")

        review_arg = "&review=%d" % review.id if review else ""

        if conflicts:
            row.td(align='left').a(href="/showcommit?sha1=%s&repository=%d%s" % (commit.sha1, repository.id, review_arg)).text("display changes relative to parents")
        else:
            row.td(align='left').a(href="/showcommit?sha1=%s&repository=%d%s&conflicts=yes" % (commit.sha1, repository.id, review_arg)).text("display conflict resolution changes")

    row = commit_info.tr("commit-info")
    row.th(align='right').text("SHA-1:")
    cell = row.td(align='left')

    if minimal:
        cell.a(href="/%s/%s?review=%d" % (repository.name, commit.sha1, review.id)).text(commit.sha1)
    else:
        cell.text(commit.sha1)

    if repository.name != user.getPreference(db, "defaultRepository"):
        cell.text(" in ")
        cell.b().text(repository.getURL(db, user))

    if not minimal:
        if review: review_arg = "&review=%d" % review.id
        else: review_arg = ""

        span = cell.span("links").span("link")
        span.text("[")
        span.a("link", href="/showtree?sha1=%s%s" % (commit.sha1, review_arg)).innerHTML("browse&nbsp;tree")
        span.text("]")

    if not review:
        outputBranches(cell.span("branches"), commit)
        outputTags(cell.span("tags"), commit)

    if minimal or commit.author.email != commit.committer.email or commit.author.time != commit.committer.time:
        row = commit_info.tr("commit-info")
        row.th(align='right').text("Author:")
        row.td(align='left').text(str(commit.author))

        if not minimal:
            row = commit_info.tr("commit-info")
            row.th(align='right').text("Commit:")
            row.td(align='left').text(str(commit.committer))
    else:
        row = commit_info.tr("commit-info")
        row.th(align='right').text("Author/Commit:")
        row.td(align='left').text(str(commit.author))

    if not minimal:
        if review: review_url_contribution = "?review=%d" % review.id
        else: review_url_contribution = ""

        for parent_sha1 in commit.parents:
            parent = gitutils.Commit.fromSHA1(db, repository, parent_sha1)

            if not review or review.containsCommit(db, parent):
                parent_href = "/%s/%s%s" % (repository.name, parent.sha1, review_url_contribution)

                row = commit_info.tr("commit-info")
                row.th(align='right').text("Parent:")
                cell = row.td(align='left')
                cell.a(href=parent_href, rel="previous").text("%s" % parent.niceSummary())
                cell.setLink("previous", parent_href)

                if not review:
                    outputBranches(cell.span("branches"), parent)
                    outputTags(cell.span("tags"), parent)

        cursor.execute("SELECT child FROM edges WHERE parent=%s", [commit.id])
        child_ids = cursor.fetchall()

        for (child_id,) in child_ids:
            if not review or review.containsCommit(db, child_id):
                try: child = gitutils.Commit.fromId(db, repository, child_id)
                except: continue

                child_href = "/%s/%s%s" % (repository.name, child.sha1, review_url_contribution)

                row = commit_info.tr("commit-info")
                row.th(align='right').text("Child:")
                cell = row.td(align='left')
                cell.a(href=child_href).text("%s" % child.niceSummary())

                if len(child_ids) == 1: cell.setLink("next", child_href)

                if not review:
                    outputBranches(cell.span("branches"), child)
                    outputTags(cell.span("tags"), child)

    def linkToCommit(commit):
        if review:
            cursor.execute("SELECT 1 FROM commits JOIN changesets ON (child=commits.id) JOIN reviewchangesets ON (changeset=changesets.id) WHERE sha1=%s AND review=%s", (commit.sha1, review.id))
            if cursor.fetchone():
                return "%s/%s?review=%d" % (repository.name, commit.sha1, review.id)
        return "%s/%s" % (repository.name, commit.sha1)

    highlight_index = 0

    if msg[0].startswith("fixup!") or msg[0].startswith("squash!"):
        for candidate_index, line in enumerate(msg[1:]):
            if line.strip():
                highlight_index = candidate_index + 1
                break

    commit_msg = commit_info.tr("commit-msg").td(colspan=2).table("commit-msg", cellspacing=0)
    for index, text in enumerate(msg):
        className = "line single"
        if index == 0: className += " first"
        elif index == len(msg) - 1: className += " last"
        if index < highlight_index or len(commit.parents) > 1:
            lengthLimit = None
        elif index == highlight_index:
            lengthLimit = "60-80"
        else:
            lengthLimit = "70-90"
        if index == highlight_index:
            className += " highlight"
        row = commit_msg.tr(className)
        row.td("edge").text()
        cell = row.td("line single commit-msg", id="msg%d" % index, critic_length_limit=lengthLimit)
        if text: cell.preformatted().text(text, linkify=linkToCommit, repository=repository)
        else: cell.text()
        row.td("edge").text()

    commit_msg.script(type="text/javascript").text("applyLengthLimit($(\"table.commit-msg td.line.commit-msg\"))");

    if review:
        chains = review_comment.loadCommentChains(db, review, user, commit=commit)

        for chain in chains:
            commit_info.addInternalScript("commentChains.push(%s);" % chain.getJSConstructor(commit.sha1))

def renderCommitFiles(db, target, user, repository, review, changeset=None, changesets=None, file_id="f%d", approve_file_id="a%d", parent_index=None, nparents=1, conflicts=False, files=None):
    def countChanges(file):
        delete_count = 0
        insert_count = 0
        if file.chunks:
            for chunk in file.chunks:
                delete_count += chunk.delete_count
                insert_count += chunk.insert_count
        return delete_count, insert_count

    commit_files = target.table("commit-files", cellspacing=0)

    if nparents > 1:
        def getpath(x): return x[1]
        def setpath(x, p): x[1] = p

        diff.File.eliminateCommonPrefixes(files, getpath=getpath, setpath=setpath)

        for data in files:
            in_parent = data[2]
            for index in range(len(in_parent)):
                file_in_parent = in_parent[index]
                if file_in_parent:
                    in_parent[index] = (file_in_parent, countChanges(file_in_parent))
                else:
                    in_parent[index] = (None, None)

        section = commit_files.thead()
        row = section.tr("parents")

        if review:
            row.th("approve").text("Reviewed")

        row.th().text("Changed Files")

        review_files = []

        for index in range(nparents):
            if conflicts and index + 1 == nparents: text = "Conflicts"
            else: text = "Parent %d" % (index + 1)

            row.th("parent", colspan=2).text(text)

            if review:
                review_files.append(changesets[index].getReviewFiles(db, user, review))

        if review:
            row.th("reviewed-by").text("Reviewed By")

        section = commit_files.tbody()

        for file_id, file_path, in_parent in files:
            row = section.tr(critic_file_id=file_id)
            fully_approved = True

            if review:
                approve = row.td("approve file")
                reviewers = {}

                for index, (file, lines) in enumerate(in_parent):
                    if file:
                        span = approve.span("parent%d" % index)

                        if review_files[index].has_key(file.id):
                            review_file = review_files[index][file.id]
                            can_approve = review_file[0]
                            is_approved = review_file[1] == "reviewed"

                            for user_id in review_file[2]:
                                reviewers[user_id] = dbutils.User.fromId(db, user_id)

                            if not is_approved: fully_approved = False
                        else:
                            can_approve = False
                            is_approved = True

                        if can_approve:
                            if is_approved: checked = "checked"
                            else: checked = None
                            input = span.input(type="checkbox", critic_parent_index=index, id="p%da%d" % (index, file.id), checked=checked)
                        elif not is_approved:
                            span.text("pending")

            row.td("path").a(href="#f%d" % file_id).innerHTML(file_path)

            for index, (file, lines) in enumerate(in_parent):
                if file:
                    if file.isBinaryChanges():
                        row.td("parent", colspan=2, critic_parent_index=index).i().text("binary")
                    elif file.isEmptyFile():
                        row.td("parent", colspan=2, critic_parent_index=index).i().text("empty")
                    elif file.old_mode == "160000" and file.new_mode == "160000":
                        if conflicts and index + 1 == nparents:
                            row.td(colspan=2).text()
                        else:
                            module_repository = repository.getModuleRepository(db, changesets[index].child, file.path)
                            if module_repository:
                                url = "/showcommit?repository=%d&from=%s&to=%s" % (module_repository.id, file.old_sha1, file.new_sha1)
                                row.td("parent", critic_parent_index=index, colspan=2).i().a(href=url).text("updated submodule")
                            else:
                                row.td("parent", critic_parent_index=index, colspan=2).i().text("updated submodule")
                    else:
                        row.td("parent", critic_parent_index=index).text(lines[0] and "-%d" % lines[0] or "")
                        row.td("parent", critic_parent_index=index).text(lines[1] and "+%d" % lines[1] or "")
                else:
                    row.td(colspan=2).text()

            if review:
                cell = row.td("reviewed-by")
                names = sorted([user.fullname for user in reviewers.values()])
                if names:
                    if fully_approved: cell.text(", ".join(names))
                    else:  cell.text("( " + ", ".join(names) + " )")
                else: cell.text()

        return

    paths = diff.File.eliminateCommonPrefixes([file.path for file in changeset.files])
    changes = map(countChanges, changeset.files)

    if review:
        review_files = changeset.getReviewFiles(db, user, review)

    additional = False
    for file in changeset.files:
        if (file.old_mode and file.new_mode and file.old_mode != file.new_mode) or (file.wasRemoved() and file.old_mode) or (file.wasAdded() and file.new_mode):
            additional = True
            break
        elif (file.old_mode and file.old_mode == "160000") or (file.new_mode and file.new_mode == "160000"):
            additional = True

    section = commit_files.thead()
    row = section.tr()
    ncolumns = 3

    if review:
        row.th("approve").text("Reviewed")
        ncolumns += 1
    row.th().text("Changed Files")
    row.th(colspan=2).text("Lines")
    if additional:
        row.th().text("Additional")
        ncolumns += 1
    if review:
        row.th().text("Reviewed By")
        ncolumns += 1

    if review:
        for is_reviewer, state, reviewers in review_files.values():
            if is_reviewer:
                can_approve_anything = True
                break
        else:
            can_approve_anything = False

    section = commit_files.tbody()
    if review and can_approve_anything:
        row = section.tr()
        checkbox_everything = row.td("approve everything").input(type="checkbox", __generator__=True)
        row.td(colspan=ncolumns - 1).i().text("Everything")
    else:
        checkbox_everything = None

    all_reviewed = True

    for file, path, lines in zip(changeset.files, paths, changes):
        row = section.tr(critic_file_id=file.id)
        fully_reviewed = True
        if parent_index is not None:
            row.setAttribute("critic-parent-index", parent_index)
        if review:
            if file.id in review_files:
                review_file = review_files[file.id]
                can_review = review_file[0]
                is_reviewed = review_file[1] == "reviewed"
                reviewers = [dbutils.User.fromId(db, user_id) for user_id in review_file[2]]
            else:
                can_review = False
                is_reviewed = True
                reviewers = []

            if not is_reviewed: fully_reviewed = False

            if can_review:
                if is_reviewed: checked = "checked"
                else:
                    checked = None
                    all_reviewed = False
                input = row.td("approve file").input(type="checkbox", critic_parent_index=parent_index, id=approve_file_id % file.id, checked=checked)
            else:
                if is_reviewed:
                    cell = row.td()
                    cell.text()
                else:
                    row.td("approve file").text("pending")

        row.td("path").a(href=("#" + file_id) % file.id).innerHTML(path)
        if file.hasChanges():
            if file.isBinaryChanges():
                row.td(colspan=2).i().text("binary")
            elif file.isEmptyFile():
                row.td(colspan=2).i().text("empty")
            else:
                row.td().text(lines[0] and "-%d" % lines[0] or "")
                row.td().text(lines[1] and "+%d" % lines[1] or "")
        else:
            row.td(colspan=2).i().text("no changes")

        if file.old_mode is not None and file.new_mode is not None and file.old_mode != file.new_mode:
            cell = row.td()
            cell.i().text("mode: ")
            cell.text("%s => %s" % (file.old_mode, file.new_mode))
        elif (file.wasRemoved() and file.old_mode) or (file.wasAdded() and file.new_mode):
            cell = row.td()
            if file.old_mode == "160000" or file.new_mode == "160000":
                cell.i().text("added submodule" if file.wasAdded() else "removed submodule")
            else:
                cell.i().text("added: " if file.wasAdded() else "removed: ")
                cell.text("%s" % file.new_mode if file.wasAdded() else file.old_mode)
        elif file.old_mode == "160000" and file.new_mode == "160000":
            module_repository = repository.getModuleRepository(db, changeset.child, file.path)
            if module_repository:
                url = "/showcommit?repository=%d&from=%s&to=%s" % (module_repository.id, file.old_sha1, file.new_sha1)
                row.td().i().a(href=url).text("updated submodule")
            else:
                row.td().i().text("updated submodule")
        elif additional:
            row.td().text()

        if review:
            cell = row.td("reviewed-by")
            names = sorted([user.fullname for user in reviewers])
            if names:
                if fully_reviewed: cell.text(", ".join(names))
                else: cell.text("( " + ", ".join(names) + " )")
            else: cell.text()

    if all_reviewed and checkbox_everything:
        checkbox_everything.setAttribute("checked", "checked")

    target.script().text("registerPathHandlers();")

def render(db, target, user, repository, review, changesets, commits, listed_commits=None, context_lines=3, is_merge=False, conflicts=False, moves=False, compact=False, wrap=True, tabify=False, profiler=None, rebases=None):
    cursor = db.cursor()

    main = target.div("main")

    options = {}

    if not user.getPreference(db, "ui.keyboardShortcuts"):
        options['show'] = True

    if user.getPreference(db, "commit.expandAllFiles"):
        options['show'] = True
        options['expand'] = True

    if compact:
        options['compact'] = True

    if tabify:
        options['tabify'] = True

    options['commit'] = changesets[0].child

    if len(changesets) == 1:
        if commits and len(commits) > 1:
            columns = [(10, log_html.WhenColumn()),
                       (5, log_html.TypeColumn()),
                       (65, log_html.SummaryColumn()),
                       (20, log_html.AuthorColumn())]

            log_html.render(db, main, "Squashed History", commits=commits, listed_commits=listed_commits, rebases=rebases, review=review, columns=columns, collapsable=True)
        elif changesets[0].parent is None or (changesets[0].parent.sha1 in changesets[0].child.parents) or conflicts:
            if conflicts and len(changesets[0].child.parents) == 1:
                commit = changesets[0].parent
            else:
                commit = changesets[0].child
            renderCommitInfo(db, main, user, repository, review, commit, conflicts)
        else:
            main.setAttribute("style", "margin-bottom: 20px; padding-bottom: 10px")

        if moves:
            def renderMoveHeaderLeft(db, target, file):
                target.text(file.move_source_file.path)
            def renderMoveHeaderRight(db, target, file):
                target.text(file.move_target_file.path)

            options['show'] = True
            options['expand'] = True
            options['support_expand'] = False
            options['header_left'] = renderMoveHeaderLeft
            options['header_right'] = renderMoveHeaderRight

            context_lines = 0
        else:
            renderCommitFiles(db, target, user, repository, review, changeset=changesets[0])

        yield target

        for stop in changeset_html.render(db, target, user, repository, changesets[0], review, context_lines=context_lines, options=options, wrap=wrap):
            yield stop
    else:
        commit = changesets[0].child

        renderCommitInfo(db, main, user, repository, review, commit)

        if profiler: profiler.check("render commit info")

        nparents = len(changesets)
        target.addInternalScript("var parentsCount = %d;" % nparents)

        files = {}

        for index, changeset in enumerate(changesets):
            for file in changeset.files:
                files.setdefault(file.id, [file.id, file.path, [None] * nparents])[2][index] = file

        renderCommitFiles(db, target, user, repository, review, changesets=changesets, file_id="p%df%%d" % index, approve_file_id="p%da%%d" % index, nparents=nparents, conflicts=changesets[-1].conflicts, files=diff.File.sorted(files.values(), key=lambda x: x[1]))

        if profiler: profiler.check("render commit files")

        mergebase = repository.mergebase(commit, db=db)

        if profiler: profiler.check("merge base")

        yield target

        relevant_commits = []

        cursor.execute("SELECT parent, file, sha1 FROM relevantcommits JOIN commits ON (relevant=id) WHERE commit=%s", (commit.getId(db),))

        rows = cursor.fetchall()

        if rows:
            for index in range(len(changesets)):
                relevant_commits.append({})

            commits_by_sha1 = {}

            for parent_index, file_id, sha1 in rows:
                if sha1 not in commits_by_sha1:
                    commits_by_sha1[sha1] = gitutils.Commit.fromSHA1(db, repository, sha1)
                relevant_commits[parent_index].setdefault(file_id, []).append(commits_by_sha1[sha1])
        else:
            values = []
            commits_by_sha1 = {}

            for index, changeset in enumerate(changesets):
                relevant_files = set([file.path for file in changeset.files])
                files = {}

                if not changeset.conflicts:
                    commit_range = "%s..%s" % (mergebase, changeset.parent.sha1)
                    relevant_lines = repository.run("log", "--name-only", "--full-history", "--format=sha1:%H", commit_range, "--", *relevant_files).splitlines()

                    for line in relevant_lines:
                        if line.startswith("sha1:"):
                            sha1 = line[5:]
                        elif line in relevant_files:
                            if sha1 not in commits_by_sha1:
                                commits_by_sha1[sha1] = gitutils.Commit.fromSHA1(db, repository, sha1)

                            relevant_commit = commits_by_sha1[sha1]
                            file_id = dbutils.find_file(db, path=line)
                            values.append((commit.getId(db), index, file_id, relevant_commit.getId(db)))
                            files.setdefault(file_id, []).append(relevant_commit)

                relevant_commits.append(files)

            cursor.executemany("INSERT INTO relevantcommits (commit, parent, file, relevant) VALUES (%s, %s, %s, %s)", values)

        if profiler: profiler.check("collecting relevant commits")

        if tabify:
            target.script(type="text/javascript").text("calculateTabWidth();")

        for index, changeset in enumerate(changesets):
            parent = target.div("parent", id="p%d" % index)

            options['support_expand'] = bool(changeset.conflicts)
            options['file_id'] = lambda base: "p%d%s" % (index, base)
            options['line_id'] = lambda base: "p%d%s" % (index, base)
            options['line_cell_id'] = lambda base: base is not None and "p%d%s" % (index, base) or None
            options['file_id_format'] = "p%df%%d" % index

            relevant_commits_per_file = {}
            for file in changeset.files:
                relevant_commits_per_file[file.id] = []
                for index1, changeset1 in enumerate(changesets):
                    if index1 != index:
                        relevant_commits_per_file[file.id].extend(relevant_commits[index1].get(file.id, []))

            if changeset.conflicts: text = "Merge conflict resolutions"
            else: text = "Changes relative to %s parent" % ("first", "second", "third", "fourth", "fifth", "seventh", "eight", "ninth")[index]

            parent.h1().text(text)

            def renderRelevantCommits(db, target, file):
                commits = relevant_commits_per_file.get(file.id)
                if commits:
                    def linkToCommit(commit, overrides={}):
                        return "%s/%s?file=%d" % (commit.repository.name, commit.sha1, file.id)

                    columns = [(70, log_html.SummaryColumn(linkToCommit=linkToCommit)),
                               (30, log_html.AuthorColumn())]

                    log_html.renderList(db, target, "Relevant Commits", commits, columns=columns, hide_merges=True, className="log relevant")

            options['content_after'] = renderRelevantCommits
            options['parent_index'] = index
            options['merge'] = True

            for stop in changeset_html.render(db, parent, user, repository, changeset,
                                              review, context_lines=context_lines,
                                              options=options, wrap=wrap, parent_index=index):
                yield stop

        if profiler: profiler.check("render diff")

    if user.getPreference(db, "ui.keyboardShortcuts"):
        page.utils.renderShortcuts(target, "showcommit",
                                   review=review,
                                   merge_parents=len(changesets),
                                   squashed_diff=commits and len(commits) > 1)

class NoChangesFound(Exception):
    pass

def commitRangeFromReview(db, user, review, filter_value, file_ids):
    edges = cursor = db.cursor()

    if filter_value == "everything":
        cursor.execute("""SELECT DISTINCT changesets.parent, changesets.child
                            FROM changesets
                            JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                           WHERE reviewchangesets.review=%s""",
                       (review.id,))
    elif filter_value == "pending":
        cursor.execute("""SELECT DISTINCT changesets.parent, changesets.child
                            FROM changesets
                            JOIN reviewfiles ON (reviewfiles.changeset=changesets.id)
                            JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                           WHERE reviewfiles.review=%s
                             AND reviewuserfiles.uid=%s
                             AND reviewfiles.state='pending'""",
                       (review.id, user.id))
    elif filter_value == "reviewable":
        cursor.execute("""SELECT DISTINCT changesets.parent, changesets.child
                            FROM changesets
                            JOIN reviewfiles ON (reviewfiles.changeset=changesets.id)
                            JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                           WHERE reviewfiles.review=%s
                             AND reviewuserfiles.uid=%s""",
                       (review.id, user.id))
    elif filter_value == "relevant":
        filters = review_filters.Filters()
        filters.setFiles(db, review=review)
        filters.load(db, review=review, user=user)

        cursor.execute("""SELECT DISTINCT changesets.parent, changesets.child, reviewfiles.file, reviewuserfiles.uid IS NOT NULL
                            FROM changesets
                            JOIN reviewfiles ON (reviewfiles.changeset=changesets.id)
                 LEFT OUTER JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id
                                                 AND reviewuserfiles.uid=%s)
                           WHERE reviewfiles.review=%s""",
                       (user.id, review.id))

        edges = set()

        for parent_id, child_id, file_id, is_reviewer in cursor:
            if is_reviewer or filters.isRelevant(user, file_id):
                edges.add((parent_id, child_id))
    elif filter_value == "files":
        assert len(file_ids) != 0

        cursor.execute("""SELECT DISTINCT changesets.parent, changesets.child
                            FROM changesets
                            JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                            JOIN fileversions ON (fileversions.changeset=changesets.id)
                           WHERE reviewchangesets.review=%s
                             AND fileversions.file=ANY (%s)""",
                       (review.id, list(file_ids)))
    else:
        raise page.utils.InvalidParameterValue(
            name="filter",
            value=filter_value,
            expected="one of 'everything', 'pending', 'reviewable', 'relevant' and 'files'")

    listed_commits = set()
    with_pending = set()

    for parent_id, child_id in edges:
        listed_commits.add(child_id)
        with_pending.add((parent_id, child_id))

    if len(listed_commits) == 1:
        commit = gitutils.Commit.fromId(db, review.repository, child_id)
        return commit.sha1, commit.sha1, list(listed_commits), listed_commits

    if filter_value in ("everything", "reviewable", "relevant", "files"):
        cursor.execute("SELECT child FROM changesets JOIN reviewchangesets ON (changeset=id) WHERE review=%s", (review.id,))
        all_commits = [gitutils.Commit.fromId(db, review.repository, commit_id) for (commit_id,) in cursor]

        commitset = CommitSet(review.branch.getCommits(db))
        tails = commitset.getFilteredTails(review.repository)

        if len(commitset) == 0:
            raise page.utils.DisplayMessage(
                title="Empty review",
                body=("This review contains no commits.  It is thus not "
                      "meaningful to display a filtered view of the changes "
                      "in it."),
                review=review)
        elif len(tails) > 1:
            ancestor = review.repository.getCommonAncestor(tails)
            paths = []

            cursor.execute("SELECT DISTINCT file FROM reviewfiles WHERE review=%s", (review.id,))
            files_in_review = set(file_id for (file_id,) in cursor)

            if filter_value == "files":
                files_in_review &= file_ids

            paths_in_review = set(dbutils.describe_file(db, file_id) for file_id in files_in_review)
            paths_in_upstreams = set()

            for tail in tails:
                paths_in_upstream = set(review.repository.run("diff", "--name-only", "%s..%s" % (ancestor, tail)).splitlines())
                paths_in_upstreams |= paths_in_upstream

                paths.append((tail, paths_in_upstream))

            overlapping_changes = paths_in_review & paths_in_upstreams

            if overlapping_changes:
                candidates = []

                for index1, data in enumerate(paths):
                    for index2, (tail, paths_in_upstream) in enumerate(paths):
                        if index1 != index2 and paths_in_upstream & paths_in_review:
                            break
                    else:
                        candidates.append(data)
            else:
                candidates = paths

            if not candidates:
                paths.sort(cmp=lambda a, b: cmp(len(a[1]), len(b[1])))

                url = "/%s/%s..%s?file=%s" % (review.repository.name, paths[0][0][:8], review.branch.head_sha1[:8], ",".join(map(str, sorted(files_in_review))))

                message = """\
<p>It is not possible to generate a diff of the requested set of
commits that contains only changes from those commits.</p>

<p>The following files would contain unrelated changes:<p>
<pre style='padding-left: 2em'>%s</pre>

<p>You can use the URL below if you want to view this diff anyway,
including the unrelated changes.</p>
<pre style='padding-left: 2em'><a href='%s'>%s%s</a></pre>""" % ("\n".join(sorted(overlapping_changes)), url, dbutils.getURLPrefix(db, user), url)

                raise page.utils.DisplayMessage(title="Impossible Diff",
                                                body=message,
                                                review=review,
                                                html=True)
            else:
                candidates.sort(cmp=lambda a, b: cmp(len(b[1]), len(a[1])))

                return candidates[0][0], review.branch.head_sha1, all_commits, listed_commits

        if tails:
            from_sha1 = tails.pop()
        else:
            # Review starts with the initial commit.
            from_sha1 = None

        return from_sha1, review.branch.head_sha1, all_commits, listed_commits

    if not with_pending:
        raise NoChangesFound()

    cursor.execute("""SELECT parent, child
                        FROM changesets
                        JOIN reviewchangesets ON (id=changeset)
                       WHERE review=%s""", (review.id,))

    children = set()
    parents = set()
    edges = {}

    for parent_id, child_id in cursor.fetchall():
        children.add(child_id)
        parents.add(parent_id)
        edges.setdefault(child_id, set()).add(parent_id)

    def isAncestorOf(ancestor_id, descendant_id):
        ancestors = edges.get(descendant_id, set()).copy()
        pending = ancestors.copy()
        while pending and ancestor_id not in ancestors:
            commit_id = pending.pop()
            parents = edges.get(commit_id, set())
            pending.update(parents - ancestors)
            ancestors.update(parents)
        return ancestor_id in ancestors

    candidates = listed_commits.copy()
    heads = set()
    tails = set()

    for candidate_id in listed_commits:
        for other_id in candidates:
            if other_id != candidate_id and isAncestorOf(candidate_id, other_id):
                break
        else:
            heads.add(candidate_id)

        for other_id in candidates:
            if other_id != candidate_id and isAncestorOf(other_id, candidate_id):
                break
        else:
            tails.add(candidate_id)

    if len(heads) != 1 or len(tails) != 1:
        raise page.utils.DisplayMessage("Filtered view not possible since it includes a merge commit.")

    head = gitutils.Commit.fromId(db, review.repository, heads.pop())
    tail = gitutils.Commit.fromId(db, review.repository, tails.pop())

    # if tail.parents greater than 1, it means it's a merge commit
    if len(tail.parents) > 1:
        raise page.utils.DisplayMessage("Filtered view not possible since it includes a merge commit.")

    if len(tail.parents) == 0:
        tail = None
    else:
        tail = gitutils.Commit.fromSHA1(db, review.repository, tail.parents[0])

    commits = getCommitList(db, review.repository, tail, head)

    if not commits:
        raise page.utils.DisplayMessage("Filtered view not possible since it includes a merge commit.")

    tail_to_return = tail.sha1 if tail is not None else None
    return tail_to_return, head.sha1, commits, listed_commits

def getCommitList(db, repository,
                  from_commit=None, to_commit=None,
                  first_commit=None, last_commit=None):
    # This function should be called with either from_commit/to_commit *or*
    # first_commit/last_commit.  The other two should be None.  When called
    # for a range that starts with a root commit, from_commit will be None
    # (and to_commit not.)
    assert (from_commit is None) or (to_commit is not None)
    assert (first_commit is None) == (last_commit is None)
    assert (to_commit is None) != (last_commit is None)

    if first_commit is not None:
        sha1s = repository.revlist(
            [last_commit], [first_commit], "--ancestry-path")
        commits = [first_commit]
        commits.extend(gitutils.Commit.fromSHA1(db, repository, sha1)
                       for sha1 in sha1s)
        return commits

    commits = set()

    class NotPossible(Exception): pass

    def process(iter_commit):
        while iter_commit != from_commit and iter_commit not in commits:
            commits.add(iter_commit)

            if len(iter_commit.parents) > 1:
                try:
                    mergebase = repository.mergebase(iter_commit)
                    # Include the parents of the merge commit (and their
                    # ancestors) if 'from_commit' is an ancestor of the merge
                    # base (but isn't the merge base.)
                    include_parents = (from_commit != mergebase and
                                       from_commit.isAncestorOf(mergebase))
                except gitutils.GitCommandError:
                    raise NotPossible

                if include_parents:
                    map(process, [gitutils.Commit.fromSHA1(db, repository, sha1) for sha1 in iter_commit.parents])
                    return
                else:
                    raise NotPossible
            else:
                if from_commit is None and len(iter_commit.parents) == 0:
                    return

                iter_commit = gitutils.Commit.fromSHA1(db, repository, iter_commit.parents[0])

    if from_commit == to_commit:
        return [to_commit]

    try:
        process(to_commit)
        return list(commits)
    except NotPossible:
        return []

def getApproximativeCommitList(db, repository, from_commit, to_commit, paths):
    try:
        ancestor = repository.getCommonAncestor([from_commit, to_commit])
    except gitutils.GitCommandError:
        return [], []

    return ([gitutils.Commit.fromSHA1(db, repository, sha1)
             for sha1 in repository.revlist([to_commit], [ancestor])],
            [gitutils.Commit.fromSHA1(db, repository, sha1).getId(db)
             for sha1 in repository.revlist([to_commit], [ancestor], paths=paths)])

def renderShowCommit(req, db, user):
    profiler = profiling.Profiler()

    files_arg = req.getParameter("file", None)
    if files_arg is None:
        file_ids = None
    else:
        file_ids = set()
        for file_arg in files_arg.split(","):
            try:
                file_id = int(file_arg)
            except ValueError:
                try:
                    file_id = dbutils.find_file(db, file_arg.strip(), insert=False)
                except dbutils.InvalidPath:
                    file_id = None
            if file_id is not None:
                file_ids.add(file_id)

    review_id = req.getParameter("review", None, filter=int)
    review_filter = req.getParameter("filter", None)
    context = req.getParameter("context", None, int)
    style = req.getParameter("style", "horizontal", str)
    rescan = req.getParameter("rescan", "no", str) == "yes"
    reanalyze = req.getParameter("reanalyze", None)
    wrap = req.getParameter("wrap", "yes", str) == "yes"
    conflicts = req.getParameter("conflicts", "no") == "yes"
    moves = req.getParameter("moves", "no") == "yes"
    full = req.getParameter("full", "no") == "yes"

    default_tabify = "yes" if user.getPreference(db, "commit.diff.visualTabs") else "no"
    tabify = req.getParameter("tabify", default_tabify) == "yes"

    if user.getPreference(db, "commit.diff.compactMode"): default_compact = "yes"
    else: default_compact = "no"

    compact = req.getParameter("compact", default_compact) == "yes"

    if moves:
        move_source_file_ids = req.getParameter("sourcefiles", None)
        move_target_file_ids = req.getParameter("targetfiles", None)

        if move_source_file_ids:
            move_source_file_ids = set(map(int, move_source_file_ids.split(",")))
        if move_target_file_ids:
            move_target_file_ids = set(map(int, move_target_file_ids.split(",")))

    all_commits = None
    listed_commits = None
    first_sha1 = None
    last_sha1 = None

    repository = None

    document = htmlutils.Document(req)
    document.setBase(None)

    if review_id is None:
        review = None
    else:
        review = dbutils.Review.fromId(db, review_id)
        if not review: raise page.utils.DisplayMessage("Invalid review ID: %d" % review_id)
        branch = review.branch
        repository = review.repository

    title = ""

    if review:
        title += "[r/%d] " % review.id

        if review_filter == "pending":
            title += "Pending: "
        elif review_filter == "reviewable":
            title += "Reviewable: "
        elif review_filter == "relevant":
            title += "Relevant: "
        elif review_filter == "everything":
            title += "Everything: "

    if not repository:
        parameter = req.getParameter("repository", None)
        if parameter:
            repository = gitutils.Repository.fromParameter(db, parameter)
            if not repository:
                raise page.utils.DisplayMessage("'%s' is not a valid repository!" % repository.name, review=review)

    cursor = db.cursor()

    def expand_sha1(sha1):
        if review and re.match("^[0-9a-f]+$", sha1):
            cursor.execute("""SELECT sha1
                                FROM commits
                                JOIN changesets ON (changesets.child=commits.id)
                                JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                               WHERE reviewchangesets.review=%s
                                 AND commits.sha1 LIKE %s""",
                           (review.id, sha1 + "%"))
            try: return cursor.fetchone()[0]
            except: pass

        if len(sha1) == 40: return sha1
        else: return repository.revparse(sha1)

    sha1 = req.getParameter("sha1", None, filter=expand_sha1)

    if sha1 is None:
        from_sha1 = req.getParameter("from", None, filter=expand_sha1)
        to_sha1 = req.getParameter("to", None, filter=expand_sha1)

        if (from_sha1 is None) != (to_sha1 is None):
            raise page.utils.DisplayMessage("invalid parameters; one of 'from'/'to' specified but not both")

        if from_sha1 is None:
            first_sha1 = req.getParameter("first", None, filter=expand_sha1)
            last_sha1 = req.getParameter("last", None, filter=expand_sha1)

            if (first_sha1 is None) != (last_sha1 is None):
                raise page.utils.DisplayMessage("invalid parameters; one of 'first'/'last' specified but not both")

            if first_sha1 is None:
                if review_id and review_filter:
                    try:
                        from_sha1, to_sha1, all_commits, listed_commits = commitRangeFromReview(db, user, review, review_filter, file_ids)
                    except NoChangesFound:
                        if review_filter == "pending":
                            raise page.utils.DisplayMessage("Your work here is done!", None, review)
                        else:
                            assert review_filter != "files"
                            raise page.utils.DisplayMessage("No %s changes found." % review_filter, None, review)
                    if from_sha1 == to_sha1:
                        sha1 = to_sha1
                        to_sha1 = None
                else:
                    raise page.utils.DisplayMessage("invalid parameters; need 'sha1', 'from'/'to' or 'first'/'last'")
    else:
        from_sha1 = None
        to_sha1 = None

    if context is None: context = user.getPreference(db, "commit.diff.contextLines")

    one_sha1 = filter(None, (sha1, from_sha1, to_sha1, first_sha1, last_sha1))[0]

    if repository:
        if not repository.iscommit(one_sha1):
            raise page.utils.DisplayMessage("'%s' is not a valid commit in the repository '%s'!" % (one_sha1, repository.name), review=review)
    else:
        repository = user.getDefaultRepository(db)
        if repository and not repository.iscommit(one_sha1):
            repository = None
        if not repository:
            repository = gitutils.Repository.fromSHA1(db, one_sha1)

    if first_sha1 is not None:
        try:
            first_commit = gitutils.Commit.fromSHA1(db, repository, first_sha1)
        except gitutils.GitReferenceError as error:
            raise page.utils.DisplayMessage("Invalid SHA-1", "%s is not a commit in %s" % (error.sha1, repository.path))

        if len(first_commit.parents) > 1:
            raise page.utils.DisplayMessage("Invalid parameters; 'first' can not be a merge commit.", review=review)

        from_sha1 = first_commit.parents[0] if first_commit.parents else None
        to_sha1 = last_sha1

    try:
        commit = gitutils.Commit.fromSHA1(db, repository, sha1) if sha1 else None
        from_commit = gitutils.Commit.fromSHA1(db, repository, from_sha1) if from_sha1 else None
        to_commit = gitutils.Commit.fromSHA1(db, repository, to_sha1) if to_sha1 else None
    except gitutils.GitReferenceError as error:
        raise page.utils.DisplayMessage("Invalid SHA-1", "%s is not a commit in %s" % (error.sha1, repository.path))

    if commit:
        title += "%s (%s)" % (commit.niceSummary(), commit.describe(db))
    elif from_commit:
        title += "%s..%s" % (from_commit.describe(db), to_commit.describe(db))
    else:
        title += "..%s" % to_commit.describe(db)

    document.setTitle(title)

    if review_filter == "pending":
        document.setLink("next", "javascript:submitChanges();")

    commits = None
    rebases = None

    profiler.check("prologue")

    if to_commit:
        changesets = changeset_utils.createChangeset(db, user, repository, from_commit=from_commit, to_commit=to_commit, conflicts=conflicts, rescan=rescan, reanalyze=reanalyze, filtered_file_ids=file_ids)
        assert len(changesets) == 1

        if not conflicts:
            if review and (review_filter in ("everything", "reviewable", "relevant")
                           or (review_filter == "files" and all_commits)):
                # We're displaying the full changes in the review (possibly
                # filtered by file) => include rebase information when rendering
                # the "Squashed History" log.

                cursor.execute(
                    """SELECT reviewrebases.id, from_head, to_head, new_upstream,
                              equivalent_merge, replayed_rebase, uid, reviewrebases.branch
                         FROM reviewrebases
                         JOIN branchupdates ON (reviewrebases.branchupdate=branchupdates.id)
                        WHERE review=%s""",
                               (review.id,))

                rebases = [
                    (rebase_id,
                     gitutils.Commit.fromId(db, repository, old_head),
                     gitutils.Commit.fromId(db, repository, new_head),
                     dbutils.User.fromId(db, user_id),
                     gitutils.Commit.fromId(db, repository, new_upstream) if new_upstream is not None else None,
                     gitutils.Commit.fromId(db, repository, equivalent_merge) if equivalent_merge is not None else None,
                     gitutils.Commit.fromId(db, repository, replayed_rebase) if replayed_rebase is not None else None,
                     branch_name)
                    for (rebase_id, old_head, new_head, new_upstream,
                         equivalent_merge, replayed_rebase, user_id, branch_name) in cursor
                ]

            if all_commits:
                commits = all_commits
            else:
                if first_sha1:
                    commits = getCommitList(
                        db, repository, first_commit=first_commit, last_commit=to_commit)
                else:
                    commits = getCommitList(
                        db, repository, from_commit=from_commit, to_commit=to_commit)

                if not commits and not review:
                    paths = [changed_file.path for changed_file in changesets[0].files]
                    commits, listed_commits = getApproximativeCommitList(db, repository, from_commit, to_commit, paths)
            if commits:
                changesets[0].setCommits(commits)
    else:
        if len(commit.parents) > 1:
            if review:
                cursor.execute("SELECT COUNT(changeset) FROM reviewchangesets JOIN changesets ON (changeset=id) WHERE review=%s AND child=%s", (review.id, commit.getId(db)))
                if cursor.fetchone()[0] > len(commit.parents):
                    full = True
        else:
            full = False

        if full:
            changesets = changeset_utils.createFullMergeChangeset(db, user, repository, commit, review=review)
            commits = [commit]
        else:
            changesets = changeset_utils.createChangeset(db, user, repository, commit=commit, rescan=rescan, reanalyze=reanalyze, conflicts=conflicts, filtered_file_ids=file_ids, review=review)
            commits = [commit]

    profiler.check("create changeset")

    if review and commits:
        all_files = set()
        pending_files = set()
        reviewable_files = set()

        cursor.execute("""SELECT reviewfiles.file, reviewfiles.state, reviewuserfiles.uid IS NOT NULL
                            FROM commits
                            JOIN changesets ON (changesets.child=commits.id)
                            JOIN reviewfiles ON (reviewfiles.changeset=changesets.id)
                 LEFT OUTER JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id AND reviewuserfiles.uid=%s)
                           WHERE commits.sha1=ANY (%s)
                             AND reviewfiles.review=%s""",
                       (user.id, [commit.sha1 for commit in commits], review.id))

        for file_id, current_state, is_reviewer in cursor:
            all_files.add(file_id)
            if is_reviewer:
                if current_state == 'pending':
                    pending_files.add(file_id)
                reviewable_files.add(file_id)

        profiler.check("reviewfiles query")

        for changeset in changesets:
            all_files_local = all_files.copy()

            for file in changeset.files:
                if file.id in all_files_local:
                    all_files_local.remove(file.id)

            for file_id in all_files_local:
                if not file_ids or file_id in file_ids:
                    changeset.files.append(diff.File(file_id, dbutils.describe_file(db, file_id), None, None, repository))

            if review_filter == "pending":
                def isPending(file): return file.id in pending_files
                changeset.files = filter(isPending, changeset.files)

            elif review_filter == "reviewable":
                def isReviewable(file): return file.id in reviewable_files
                changeset.files = filter(isReviewable, changeset.files)

            elif review_filter == "relevant":
                filters = review_filters.Filters()
                filters.setFiles(db, review=review)
                filters.load(db, review=review, user=user)

                def isRelevant(file):
                    if file.id in reviewable_files: return True
                    elif filters.isRelevant(user, file): return True
                    else: return False

                changeset.files = filter(isRelevant, changeset.files)

            elif review_filter == "files":
                def isFiltered(file): return file.id in file_ids
                changeset.files = filter(isFiltered, changeset.files)

        profiler.check("review filtering")

    if moves:
        if len(changesets) != 1:
            raise page.utils.DisplayMessage("Can't detect moves in a merge commit!", review=review)

        move_changeset = changeset_detectmoves.detectMoves(db, changesets[0], move_source_file_ids, move_target_file_ids)

        if not move_changeset:
            raise page.utils.DisplayMessage("No moved code found!", review=review)

        changesets = [move_changeset]

        profiler.check("moves detection")

    html = document.html()
    head = html.head()
    body = html.body()

    if review:
        def generateButtons(target):
            review_utils.renderDraftItems(db, user, review, target)
            buttons = target.div("buttons")
            if user.getPreference(db, "debug.extensions.customProcessCommits"):
                buttons.button(onclick='customProcessCommits();').text("Process Commits")
            buttons.span("buttonscope buttonscope-global")
        page.utils.generateHeader(body, db, user, generateButtons, extra_links=[("r/%d" % review.id, "Back to Review")])
    else:
        def generateButtons(target):
            buttons = target.div("buttons")
            if not user.isAnonymous() and (commit or commits):
                buttons.button(onclick='createReview();').text('Create Review')
            buttons.span("buttonscope buttonscope-global")
        page.utils.generateHeader(body, db, user, generateButtons)

    log_html.addResources(document)
    changeset_html.addResources(db, user, repository, review, compact, tabify, document)

    document.addInternalScript(user.getJS(db))
    document.addInternalScript(repository.getJS())
    document.addInternalScript("var keyboardShortcuts = %s;" % (user.getPreference(db, "ui.keyboardShortcuts") and "true" or "false"))

    for stop in render(db, body, user, repository, review, changesets, commits, listed_commits, context_lines=context, conflicts=conflicts, moves=moves, compact=compact, wrap=wrap, tabify=tabify, profiler=profiler, rebases=rebases):
        yield document.render(stop=stop, pretty=not compact)

    profiler.check("rendering")
    profiler.output(db, user, document)

    db.commit()

    yield document.render(pretty=not compact)
