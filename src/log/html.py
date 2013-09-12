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

from gitutils import Commit
from htmlutils import htmlify, jsify
from profiling import Profiler
from time import time, mktime, strftime, localtime

import re
import dbutils
import log.commitset

def formatWhen(when):
    def inner(when):
        delta = int(time() - mktime(when))
        if delta < 60: return "%d seconds ago" % delta
        elif delta < 60 * 60: return "%d minutes ago" % (delta / 60)
        elif delta < 60 * 60 * 24: return "%d hours ago" % (delta / (60 * 60))
        elif delta < 60 * 60 * 24 * 30: return "%d days ago" % (delta / (60 * 60 * 24))
        else: return strftime("%Y-%m-%d", localtime(mktime(when)))
    return inner(when).replace(" ", "&nbsp;")

def renderWhen(target, when):
    target.innerHTML(formatWhen(when))

def linkToCommit(commit, overrides={}):
    return "%s/%s" % (commit.repository.name, commit.sha1)

re_remote_into_local = re.compile("^Merge (?:branch|commit) '([^']+)' of [^ ]+ into \\1$")
re_side_into_main = re.compile("^Merge (?:remote )?(?:branch|commit) '[^']+' into .+$")
re_octopus = re.compile("^Merge ((?:(?:branches|,| and) '[^']+')+) into [^ ]+$")

class WhenColumn:
    def className(self, db, commit):
        return "when"
    def heading(self, target):
        target.text("When")
    def render(self, db, commit, target, overrides={}):
        renderWhen(target, commit.committer.time)

class TypeColumn:
    def className(self, db, commit):
        return "type"
    def heading(self, target):
        target.text()
    def render(self, db, commit, target, overrides={}):
        if "type" in overrides: target.text(overrides["type"])
        if len(commit.parents) > 1: target.text("Merge")
        else: target.text()

class SummaryColumn:
    def __init__(self, linkToCommit=linkToCommit):
        self.linkToCommit = linkToCommit
        self.isFixupOrSquash = None
    def className(self, db, commit):
        return "summary"
    def heading(self, target):
        target.text("Summary")
    def render(self, db, commit, target, overrides={}):
        summary = overrides.get("summary", commit.summary())
        classnames = ["commit"] + overrides.get("summary_classnames", [])

        if self.isFixupOrSquash is not None:
            data = self.isFixupOrSquash(commit)
            if data:
                what, ref_commit = data
                target.span(what, critic_ref=ref_commit.summary()).text("[%s] " % what)
                lines = commit.message.splitlines()[1:]
                while lines and not lines[0].strip():
                    lines.pop(0)
                if lines: summary = lines[0]
                else: summary = None
                if not summary:
                    classnames.append("nocomment")
                    summary = "(no comment)"

        url = self.linkToCommit(commit, overrides)

        if summary:
            target.a(" ".join(classnames), href=url).text(summary)

class AuthorColumn:
    def __init__(self):
        self.cache = {}
    def className(self, db, commit):
        return "author"
    def heading(self, target):
        target.text("Author")
    def render(self, db, commit, target, overrides={}):
        if "author" in overrides:
            user = overrides["author"]
        else:
            email = commit.author.email
            user = self.cache.get(email)
        if not user:
            user_id = commit.author.getUserId(db)
            if user_id is None:
                target.text(commit.author.name)
                return
            else:
                user = self.cache[email] = dbutils.User.fromId(db, user_id)
        target.text(user.fullname)

DEFAULT_COLUMNS = [(10, WhenColumn()),
                   (5, TypeColumn()),
                   (65, SummaryColumn()),
                   (20, AuthorColumn())]

def render(db, target, title, branch=None, commits=None, columns=DEFAULT_COLUMNS, title_right=None, listed_commits=None, rebases=None, branch_name=None, bottom_right=None, review=None, highlight=None, profiler=None, collapsable=False, user=None, extra_commits=None, conflicts=set()):
    addResources(target)

    if not profiler: profiler = Profiler()

    profiler.check("log: start")

    if branch is not None:
        repository = branch.repository
        branch.loadCommits(db)
        commits = branch.commits[:]
        commit_set = log.commitset.CommitSet(branch.commits)
    else:
        assert commits is not None
        repository = commits[0].repository if len(commits) else None
        commit_set = log.commitset.CommitSet(commits)

    profiler.check("log: commits")

    heads = commit_set.getHeads()
    tails = commit_set.getTails()

    rebase_old_heads = set()

    if rebases:
        class Rebase(object):
            def __init__(self, rebase_id, old_head, new_head, user,
                         new_upstream, target_branch_name):
                self.id = rebase_id
                self.old_head = Commit.fromId(db, repository, old_head)
                self.new_head = Commit.fromId(db, repository, new_head)
                self.user = user
                self.new_upstream = new_upstream and Commit.fromId(db, repository, new_upstream)
                self.target_branch_name = target_branch_name

        # The first element in the tuples in 'rebases' is the rebase id, which
        # is an ever-increasing serial number that we can use as an indication
        # of the order in which the rebases were made.
        rebases = [Rebase(*rebase) for rebase in sorted(rebases)]
        rebase_old_heads = set(rebase.old_head for rebase in rebases)
        heads -= rebase_old_heads

        assert 0 <= len(heads) <= 1

        if not heads:
            heads = set([rebases[-1].new_head])

    if repository:
        target.addInternalScript(repository.getJS())

    processed = set()
    summaries = {}

    for commit in commits:
        summary = commit.summary().strip()
        summaries[summary] = commit
        if len(summary) > 60:
            summaries[summary[:40]] = commit
        summaries[commit.sha1] = commit
        summaries[commit.sha1[:8]] = commit

    if extra_commits:
        for commit in extra_commits:
            summary = commit.summary().strip()
            summaries[summary] = commit
            if len(summary) > 60:
                summaries[summary[:40]] = commit
            summaries[commit.sha1] = commit
            summaries[commit.sha1[:8]] = commit

    def isFixupOrSquash(commit):
        if commit.message.startswith("fixup! "):
            what = "fixup"
            summary = commit.summary()[6:].strip()
        elif commit.message.startswith("squash! "):
            what = "squash"
            summary = commit.summary()[7:].strip()
        else:
            return None

        commit = (summaries.get(summary) or
                  summaries.get(summary[:40]) or
                  summaries.get(summary[:8]))

        if commit: return what, commit
        else: return None

    for width, column in columns:
        if isinstance(column, SummaryColumn):
            column.isFixupOrSquash = isFixupOrSquash
            break

    def output(table, commit, overrides={}):
        if commit not in processed:
            classes = ["commit"]
            row_id = None

            if len(commit.parents) > 1:
                classes.append("merge")

            if highlight == commit:
                classes.append("highlight")
                row_id = commit.sha1

            row = table.tr(" ".join(classes), id=row_id)
            profiler.check("log: rendering: row")
            for index, (width, column) in enumerate(columns):
                column.render(db, commit, row.td(column.className(db, commit)), overrides=overrides)
                profiler.check("log: rendering: column %d" % (index + 1))
            processed.add(commit)

            return row
        else:
            return None

    cursor = db.cursor()

    def emptyCommit(commit):
        cursor.execute("""SELECT 1
                            FROM fileversions
                            JOIN changesets ON (changesets.id=fileversions.changeset)
                            JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                           WHERE changesets.child=%s
                             AND reviewchangesets.review=%s""",
                       (commit.getId(db), review.id))
        return not cursor.fetchone()

    def inner(target, head, tails, align='right', title=None, table=None, silent_if_empty=set(), upstream=None):
        if not table:
            table = target.table('log', align=align, cellspacing=0)

            for width, column in columns: table.col(width=('%d%%' % width))

            if title:
                thead = table.thead()
                row = thead.tr("title")
                header = row.td("h1", colspan=len(columns)).h1()
                header.text(title)
                if callable(title_right):
                    title_right(db, header.span("right"))

                row = thead.tr('headings')
                for width, column in columns:
                    column.heading(row.td(column.className(db, None)))
            elif head is None or head in tails:
                if upstream:
                    tag = upstream.findInterestingTag(db)
                    if tag: what = tag
                    else: what = upstream.sha1[:8]
                    message = "Merged with base branch (%s)." % what
                else: message = "Merged with base branch."

                thead = table.thead()
                row = thead.tr('basemerge')
                row.td(colspan=len(columns), align='center').text(message)
                return (None, None, None, False)

        tbody = table.tbody()
        commit = head

        last_commit = None
        skipped = True

        while commit and commit not in tails:
            suppress = False
            optional_merge = False
            listed = listed_commits is None or commit.getId(db) in listed_commits

            if commit in silent_if_empty and emptyCommit(commit):
                # This is a clean automatically generated merge commit; pretend it isn't here at all.
                suppress = True

            if not suppress and not listed:
                suppress = len(commit.parents) == 1
                optional_merge = not suppress

            if not suppress: commit_tr = output(tbody, commit)
            else: commit_tr = None

            if listed: skipped = False
            last_commit = commit

            if len(commit.parents) == 0:
                break
            elif len(commit.parents) == 1:
                commit = commit_set.get(commit.parents[0])
            elif len(commit.parents) > 1:
                if len(commit.parents) > 2:
                    common_ancestors = commit_set.getCommonAncestors(commit)
                    match = re_octopus.match(commit.message.split("\n", 1)[0])

                    if match:
                        titles = re.findall("'([^']+)'", match.group(1))
                        if len(titles) != len(commit.parents):
                            titles = None
                    else:
                        titles = None

                    for index, sha1 in enumerate(commit.parents):
                        if sha1 in commit_set:
                            sublog = tbody.tr('sublog')
                            inner_last_commit, inner_table, inner_tail, inner_skipped = inner(sublog.td(colspan=len(columns)), commit_set[sha1], common_ancestors, title=titles and titles[index] or None)
                            if inner_skipped:
                                sublog.remove()
                                if optional_merge and commit_tr: commit_tr.remove()

                    if not common_ancestors: return (None, None, None, False)

                    commit = common_ancestors.pop()
                    continue

                parent1_sha1 = commit.parents[0]
                parent2_sha1 = commit.parents[1]

                parent1 = commit_set.get(parent1_sha1)
                parent2 = commit_set.get(parent2_sha1)

                # TODO: Try to remember what this code actually does, and why...
                if parent1_sha1 in rebase_old_heads:
                    if parent2:
                        sublog = tbody.tr('sublog')
                        inner_last_commit, inner_table, inner_tail, inner_skipped = \
                            inner(sublog.td(colspan=len(columns)), parent2, tails)
                        if inner_skipped:
                            sublog.remove()
                            if optional_merge and commit_tr: commit_tr.remove()
                    return (commit, table, parent1_sha1, False)
                elif parent2_sha1 in rebase_old_heads:
                    if parent1:
                        sublog = tbody.tr('sublog')
                        inner_last_commit, inner_table, inner_tail, inner_skipped = \
                            inner(sublog.td(colspan=len(columns)), parent1, tails)
                        if inner_skipped:
                            sublog.remove()
                            if optional_merge and commit_tr: commit_tr.remove()
                    return (commit, table, parent2_sha1, False)

                if parent1 and parent2:
                    common_ancestors = commit_set.getCommonAncestors(commit)

                    merged_remote_into_local = re_remote_into_local.match(commit.summary()) or re_side_into_main.match(commit.summary())

                    def rankPaths(commit, tails):
                        shortest = None
                        shortest_length = len(commit_set)
                        longest = None
                        longest_length = 0

                        for sha1 in commit.parents:
                            parent = commit_set[sha1]

                            counted = set()
                            pending = set([parent])

                            while pending:
                                candidate = pending.pop()

                                if candidate in counted: continue
                                if candidate in tails: continue

                                counted.add(candidate)
                                pending.update(commit_set.getParents(candidate))

                            length = len(counted)

                            if length < shortest_length:
                                shortest = parent
                                shortest_length = length
                            if length >= longest_length:
                                longest = parent
                                longest_length = length

                        return shortest, shortest_length, longest, longest_length

                    show_merged, shortest_length, show_normal, longest_length = rankPaths(commit, common_ancestors | tails)
                    display_parallel = False

                    if merged_remote_into_local and shortest_length * 2 > longest_length:
                        if len(common_ancestors) == 1 and len(commit_set.filtered([commit]).getTails()) == 1:
                            display_parallel = True
                        else:
                            show_merged = parent2
                            show_normal = parent1

                    if display_parallel:
                        all_empty = True

                        for sha1 in commit.parents:
                            sublog = tbody.tr('sublog')
                            inner_last_commit, inner_table, inner_tail, inner_skipped = inner(sublog.td(colspan=len(columns)), commit_set[sha1], common_ancestors | tails)
                            if inner_skipped:
                                sublog.remove()
                            else:
                                all_empty = False

                        if all_empty and optional_merge and commit_tr: commit_tr.remove()

                        commit = common_ancestors.pop()
                    else:
                        sublog = tbody.tr('sublog')
                        inner_last_commit, inner_table, inner_tail, inner_skipped = inner(sublog.td(colspan=len(columns)), show_merged, common_ancestors | tails)
                        if inner_skipped:
                            sublog.remove()
                            if optional_merge and commit_tr: commit_tr.remove()

                        commit = show_normal
                else:
                    if parent1: upstream_sha1 = parent2_sha1
                    else: upstream_sha1 = parent1_sha1

                    if not commit in silent_if_empty:
                        # Merge with the base branch.
                        inner(tbody.tr('sublog').td(colspan=len(columns)), None, None, upstream=Commit.fromSHA1(db, repository, upstream_sha1))

                    if parent1: commit = parent1
                    else: commit = parent2

        return (last_commit, table, last_commit.parents[0] if last_commit and last_commit.parents else None, skipped)

    class_name = "paleyellow log"

    if collapsable:
        class_name += " collapsable"

    table = target.table(class_name, align='center', cellspacing=0)

    for width, column in columns: table.col(width=('%d%%' % width))

    thead = table.thead("title")
    row = thead.tr("title")
    header = row.td("h1", colspan=len(columns)).h1()

    error_message = None

    if len(commit_set) == 0:
        thead = table.thead()
        row = thead.tr('error')
        cell = row.td(colspan=len(columns), align='center')
        cell.text("No commits. ")
        if review:
            review.branch.loadCommits(db)
            cell.a(href="showtree?sha1=%s&review=%d" % (review.branch.head.sha1, review.id)).text("[Browse tree]")
        return
    elif len(heads) > 1:
        error_message = "Invalid commit set: Multiple heads."
    elif len(heads) == 0:
        error_message = "Invalid commit set: No heads."

    if error_message is not None:
        thead = table.thead()
        row = thead.tr('error')
        cell = row.td(colspan=len(columns), align='center')
        cell.text(error_message)
        return

    head = heads.pop() if heads else None

    row = thead.tr('headings')
    for width, column in columns:
        column.heading(row.td(column.className(db, None)))

    first_rebase = True
    silent_if_empty = set()

    if rebases:
        for rebase in rebases:
            if rebase.new_upstream or rebase.target_branch_name:
                silent_if_empty.add(rebase.old_head)

        top_rebases = []

        while head == rebases[-1].new_head:
            rebase = rebases.pop()
            top_rebases.append((head, rebase))
            head = rebase.old_head
            if head in commit_set:
                break

        for rebase_head, rebase in top_rebases:
            thead = table.thead("rebase")
            row = thead.tr('rebase')
            cell = row.td(colspan=len(columns), align='center')

            if rebase.new_upstream is None and not rebase.target_branch_name:
                cell.text("History rewritten")
            else:
                cell.text("Branch rebased onto ")
                if rebase.target_branch_name:
                    anchor = cell.a(href=("/checkbranch?repository=%d&commit=%s"
                                          % (repository.id, rebase.target_branch_name)))
                    anchor.text(rebase.target_branch_name)
                else:
                    upstream_description = repository.describe(db, rebase.new_upstream.sha1)
                    if upstream_description is None:
                        upstream_description = rebase.new_upstream.sha1[:8]
                    anchor = cell.a(href="/%s/%s" % (repository.name, rebase.new_upstream.sha1))
                    anchor.text(upstream_description)

            cell.text(" by %s" % rebase.user.fullname)

            if first_rebase:
                cell.text(": ")
                review_param = "&review=%d" % review.id if review else ""
                cell.a(href="log?repository=%d&branch=%s%s" % (repository.id, branch_name, review_param)).text("[actual log]")

                if user and user == rebase.user:
                    cell.text(" ")
                    cell.a(href="javascript:revertRebase(%d)" % rebase.id).text("[revert]")

                first_rebase = False
            else:
                cell.text(".")

            if rebase.new_head in conflicts and not emptyCommit(rebase.new_head):
                output(table, rebase.new_head,
                       overrides={ "type": "Rebase",
                                   "summary": "Changes introduced by rebase",
                                   "summary_classnames": ["rebase"],
                                   "author": rebase.user,
                                   "rebase_conflicts": conflicts[rebase.new_head] })

    while True:
        # 'local_tails' is the set of commits that, when reached, should make
        # inner() stop outputting commits and instead return.  This set of
        # commits contains all the "tails" of the whole commit-set we're
        # rendering (in the 'tails' set here), as well as the "new head" of the
        # next rebase to be output.

        local_tails = tails.copy()

        if rebases:
            local_tails.add(rebases[-1].new_head)

        last_commit, table, tail, skipped = inner(
            target, head, local_tails, 'center', title, table, silent_if_empty)

        if rebases:
            rebase = rebases.pop()

            assert tail == rebase.new_head, "tail (%s) != rebase.new_head (%s)" % (tail, rebase.new_head)

            while True:
                head = rebase.old_head

                thead = table.thead("rebase")
                row = thead.tr('rebase')
                cell = row.td(colspan=len(columns), align='center')

                if rebase.new_upstream is None and not rebase.target_branch_name:
                    cell.text("History rewritten")
                else:
                    cell.text("Branch rebased onto ")
                    if rebase.target_branch_name:
                        anchor = cell.a(href=("/checkbranch?repository=%d&commit=%s"
                                              % (repository.id, rebase.target_branch_name)))
                        anchor.text(rebase.target_branch_name)
                    else:
                        upstream_description = repository.describe(db, rebase.new_upstream.sha1)
                        if upstream_description is None:
                            upstream_description = rebase.new_upstream.sha1[:8]
                        anchor = cell.a(href="/%s/%s" % (repository.name, rebase.new_upstream.sha1))
                        anchor.text(upstream_description)

                cell.text(" by %s" % rebase.user.fullname)

                if first_rebase:
                    cell.text(": ")
                    review_param = "&review=%d" % review.id if review else ""
                    cell.a(href="log?repository=%d&branch=%s%s" % (repository.id, branch_name, review_param)).text("[actual log]")
                    first_rebase = False
                else:
                    cell.text(".")

                if rebase.new_head in conflicts:
                    if len(rebase.new_head.parents) < 2 and not emptyCommit(rebase.new_head):
                        output(table, rebase.new_head,
                               overrides={ "type": "Rebase",
                                           "summary": "Changes introduced by rebase",
                                           "summary_classnames": ["rebase"],
                                           "author": rebase.user,
                                           "rebase_conflicts": conflicts[rebase.new_head] })

                if rebases and rebases[-1].new_head == head:
                    rebase = rebases.pop()
                else:
                    break

            continue

        if last_commit:
            if len(last_commit.parents) == 1:
                upstream = Commit.fromSHA1(db, repository, last_commit.parents[0])
                upstream_description = repository.describe(db, upstream.sha1)

                if not upstream_description:
                    upstream_description = upstream.sha1[:8]

                row = table.thead("rebase").tr('upstream')
                cell = row.td(colspan=len(columns), align='center')
                cell.text("Based on: ")
                anchor = cell.a(href="/%s/%s" % (repository.name, upstream.sha1))
                anchor.text(upstream_description)

        if callable(bottom_right):
            bottom_right(db, table.tfoot().tr().td(colspan=len(columns)))

        break

    profiler.check("log: rendering")

    if "%d" in title: header.text(title % len(processed))
    else: header.text(title)

    if callable(title_right):
        title_right(db, header.span("right"))

def renderList(db, target, title, commits, columns=DEFAULT_COLUMNS, title_right=None, bottom_right=None, hide_merges=False, className="log"):
    addResources(target)

    table = target.table(className, align="center", cellspacing=0)

    for width, column in columns: table.col(width=("%d%%" % width))

    thead = table.thead()
    title_h1 = None

    if title:
        row = thead.tr("title")
        title_h1 = row.td("h1", colspan=len(columns)).h1()
        title_h1.text(title)

        row = thead.tr("headings")
        for width, column in columns:
            column.heading(row.td(column.className(db, None)))

    tbody = table.tbody()
    merges = 0

    for commit in commits:
        classname = "commit"

        if hide_merges:
            is_merge = len(commit.parents) > 1
            if is_merge:
                classname += " merge"
                merges += 1

        row = tbody.tr(classname, id=commit.sha1)

        for width, column in columns:
            column.render(db, commit, row.td(column.className(db, commit)))

    if merges and title_h1:
        title_h1.a(href="javascript:void(0);", onclick="showRelevantMerges(event);").text("[Show %d merge commits]" % merges)

    if callable(title_right):
        title_right(db, title_h1.span("right"))

    if callable(bottom_right):
        bottom_right(db, table.tfoot().tr().td(colspan=len(columns)))

def addResources(target):
    target.addExternalStylesheet("resource/log.css")
    target.addExternalScript("resource/log.js")
