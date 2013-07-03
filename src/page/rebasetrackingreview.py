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

import page
import htmlutils
import gitutils
import request

from page.parameters import Optional, ReviewId

class RebaseTrackingReview(page.Page):
    def __init__(self):
        super(RebaseTrackingReview, self).__init__("rebasetrackingreview",
                                                   { "review": ReviewId,
                                                     "newbranch": Optional(str),
                                                     "upstream": Optional(str),
                                                     "newhead": Optional(str),
                                                     "newupstream": Optional(str) },
                                                   RebaseTrackingReview.Handler)

    class Handler(page.Page.Handler):
        def __init__(self, review, newbranch=None, upstream=None, newhead=None, newupstream=None):
            super(RebaseTrackingReview.Handler, self).__init__(review)
            self.newbranch = newbranch
            self.upstream = upstream
            self.newhead = newhead
            self.newupstream = newupstream

        def generateHeader(self):
            self.document.addExternalStylesheet("resource/rebasetrackingreview.css")
            self.document.addExternalScript("resource/autocomplete.js")
            self.document.addExternalScript("resource/rebasetrackingreview.js")

        def generateContent(self):
            trackedbranch = self.review.getTrackedBranch(self.db)

            if not trackedbranch:
                raise request.DisplayMessage("Not supported!", "The review r/%d is not tracking a remote branch." % self.review.id)

            self.document.addInternalScript(self.review.repository.getJS())
            self.document.addInternalScript(self.review.getJS())
            self.document.addInternalScript("var trackedbranch = { remote: %s, name: %s };"
                                            % (htmlutils.jsify(trackedbranch.remote),
                                               htmlutils.jsify(trackedbranch.name)))

            table = page.utils.PaleYellowTable(self.body, "Rebase tracking review")

            def renderRemote(target):
                target.span("value", id="remote").text(trackedbranch.remote)
            def renderCurrentBranch(target):
                target.span("value", id="currentbranch").text("refs/heads/" + trackedbranch.name)

            table.addItem("Remote", renderRemote)
            table.addItem("Current branch", renderCurrentBranch)
            table.addSeparator()

            if self.newbranch is not None and self.upstream is not None and self.newhead is not None and self.newupstream is not None:
                import log.html
                import log.commitset

                sha1s = self.review.repository.revlist(included=[self.newhead], excluded=[self.newupstream])
                new_commits = log.commitset.CommitSet(gitutils.Commit.fromSHA1(self.db, self.review.repository, sha1) for sha1 in sha1s)

                new_heads = new_commits.getHeads()
                if len(new_heads) != 1:
                    raise page.utils.DisplayMessage("Invalid commit-set!", "Multiple heads.  (This ought to be impossible...)")
                new_upstreams = new_commits.getFilteredTails(self.review.repository)
                if len(new_upstreams) != 1:
                    raise page.utils.DisplayMessage("Invalid commit-set!", "Multiple upstreams.  (This ought to be impossible...)")

                new_head = new_heads.pop()
                new_upstream_sha1 = new_upstreams.pop()

                old_commits = log.commitset.CommitSet(self.review.branch.commits)
                old_upstreams = old_commits.getFilteredTails(self.review.repository)

                if len(old_upstreams) != 1:
                    raise page.utils.DisplayMessage("Rebase not supported!", "The review has mulitple upstreams and can't be rebased.")

                if len(old_upstreams) == 1 and new_upstream_sha1 in old_upstreams:
                    # This appears to be a history rewrite.
                    new_upstream = None
                    new_upstream_sha1 = None
                    rebase_type = "history"
                else:
                    old_upstream = gitutils.Commit.fromSHA1(self.db, self.review.repository, old_upstreams.pop())
                    new_upstream = gitutils.Commit.fromSHA1(self.db, self.review.repository, new_upstream_sha1)

                    if old_upstream.isAncestorOf(new_upstream):
                        rebase_type = "move:ff"
                    else:
                        rebase_type = "move"

                self.document.addInternalScript("var check = { rebase_type: %s, old_head_sha1: %s, new_head_sha1: %s, new_upstream_sha1: %s, new_trackedbranch: %s };"
                                                % (htmlutils.jsify(rebase_type),
                                                   htmlutils.jsify(self.review.branch.head.sha1),
                                                   htmlutils.jsify(new_head.sha1),
                                                   htmlutils.jsify(new_upstream_sha1),
                                                   htmlutils.jsify(self.newbranch[len("refs/heads/"):])))

                def renderNewBranch(target):
                    target.span("value", id="newbranch").text(self.newbranch)
                    target.text(" @ ")
                    target.span("value").text(new_head.sha1[:8] + " " + new_head.niceSummary())
                def renderUpstream(target):
                    target.span("value", id="upstream").text(self.upstream)
                    target.text(" @ ")
                    target.span("value").text(new_upstream.sha1[:8] + " " + new_upstream.niceSummary())

                table.addItem("New branch", renderNewBranch)

                if new_upstream:
                    table.addItem("New upstream", renderUpstream)

                table.addSeparator()

                def renderMergeStatus(target):
                    target.a("status", id="status_merge").text("N/A")
                def renderConflictsStatus(target):
                    target.a("status", id="status_conflicts").text("N/A")
                def renderHistoryRewriteStatus(target):
                    target.a("status", id="status_historyrewrite").text("N/A")

                table.addSection("Status")

                if rebase_type == "history":
                    table.addItem("History rewrite", renderHistoryRewriteStatus)
                else:
                    if rebase_type == "move:ff":
                        table.addItem("Merge", renderMergeStatus)
                    table.addItem("Conflicts", renderConflictsStatus)

                def renderRebaseReview(target):
                    target.button(id="rebasereview", onclick="rebaseReview();", disabled="disabled").text("Rebase Review")

                table.addSeparator()
                table.addCentered(renderRebaseReview)

                log.html.render(self.db, self.body, "Rebased commits", commits=list(new_commits))
            else:
                try:
                    from customization.branches import getRebasedBranchPattern
                except ImportError:
                    def getRebasedBranchPattern(branch_name): return None

                pattern = getRebasedBranchPattern(trackedbranch.name)

                try:
                    from customization.branches import isRebasedBranchCandidate
                except ImportError:
                    isRebasedBranchCandidate = None

                if pattern or isRebasedBranchCandidate:
                    candidates = [name[len("refs/heads/"):]
                                  for sha1, name in gitutils.Repository.lsremote(trackedbranch.remote, pattern=pattern, include_heads=True)
                                  if name.startswith("refs/heads/")]

                    if isRebasedBranchCandidate is not None:
                        def isCandidate(name):
                            return isRebasedBranchCandidate(trackedbranch.name, name)

                        candidates = filter(isCandidate, candidates)
                else:
                    candidates = []

                if len(candidates) > 1:
                    def renderCandidates(target):
                        target.text("refs/heads/")
                        dropdown = target.select(id="newbranch")
                        for name in candidates:
                            dropdown.option(value=name).text(name)

                    table.addItem("New branch", renderCandidates,
                                    buttons=[("Edit", "editNewBranch(this);")])
                else:
                    if len(candidates) == 1:
                        default_value = candidates[0]
                    else:
                        default_value = trackedbranch.name

                    def renderEdit(target):
                        target.text("refs/heads/")
                        target.input(id="newbranch", value=default_value)

                    table.addItem("New branch", renderEdit)

                def renderUpstreamInput(target):
                    target.input(id="upstream", value="refs/heads/master")

                table.addItem("Upstream", renderUpstreamInput)

                def renderFetchBranch(target):
                    target.button(onclick="fetchBranch();").text("Fetch Branch")

                table.addSeparator()
                table.addCentered(renderFetchBranch)

