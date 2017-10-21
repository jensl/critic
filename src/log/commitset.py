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

import gitutils

class CommitSet:
    def __init__(self, commits):
        self.__commits = dict([(str(commit), commit) for commit in commits])
        self.__merges = set()
        self.__children = {}

        parents = set()

        for commit in self.__commits.values():
            for parent in commit.parents:
                parents.add(parent)
                self.__children.setdefault(parent, set()).add(commit)
            if len(commit.parents) > 1:
                self.__merges.add(commit)

        commit_set = set(self.__commits.values())

        # Heads: commits that aren't the parent of a commit in the set.
        self.__heads = commit_set - parents

        # Tails: parent commits not included in the set.
        self.__tails = parents - commit_set

    def __contains__(self, commit):
        return str(commit) in self.__commits

    def __getitem__(self, key):
        return self.__commits[str(key)]

    def __len__(self):
        return len(self.__commits)

    def __iter__(self):
        return iter(self.__commits.values())

    def __repr__(self):
        return repr(self.__commits)

    @staticmethod
    def union(*commit_sets):
        commits = set()
        for commit_set in commit_sets:
            commits.update(commit_set.__commits.values())
        return CommitSet(commits)

    def get(self, key):
        return self.__commits.get(str(key))

    def getHeads(self):
        return self.__heads.copy()

    def getTails(self):
        return self.__tails.copy()

    def getMerges(self):
        return self.__merges.copy()

    def getChildren(self, commit):
        children = self.__children.get(commit)
        if children: return children.copy()
        else: return set()

    def getParents(self, commit):
        return set([self.__commits[sha1] for sha1 in commit.parents if sha1 in self.__commits])

    def getFilteredTails(self, repository):
        """Return a set containing each tail commit of the set of commits that isn't an
ancestor of another tail commit of the set.  If the tail commits of the set
are all different commits on an upstream branch, then this will return only
the latest one."""

        candidates = self.getTails()
        result = set()

        while candidates:
            tail = candidates.pop()

            eliminated = set()
            for other in candidates:
                base = repository.mergebase([tail, other])
                if base == tail:
                    # Tail is an ancestor of other: tail should not be included
                    # in the returned set.
                    break
                elif base == other:
                    # Other is an ancestor of tail: other should not be included
                    # in the returned set.
                    eliminated.add(other)
            else:
                result.add(tail)
            candidates -= eliminated

        return result

    def getTailsFrom(self, commit):
        """
        Return a set containing the each tail commit of the set of commits that
        are ancestors of 'commit' and that are members of this commit set.

        A tail commit of a set is a commit that is not a member of the set but
        that is a parent of a commit that is a member of the set.
        """

        assert commit in self.__commits

        stack = set([commit.sha1])
        processed = set()
        tails = set()

        while stack:
            commit = self.__commits[stack.pop()]

            if commit not in processed:
                processed.add(commit)

                for sha1 in commit.parents:
                    parent = self.__commits.get(sha1)
                    if parent: stack.add(parent)
                    else: tails.add(sha1)

        return tails

    def getCommonAncestors(self, commit):
        """Return a set of each commit in this set that is an ancestor of each parent of
'commit' (which must be a member of the set) or None if the parents of 'commit'
have no common ancestor within this set."""

        common_ancestors = set()
        branches = []

        for sha1 in commit.parents:
            if sha1 not in self.__commits: return common_ancestors
            branches.append(set())

        for index, sha1 in enumerate(commit.parents):
            stack = set([sha1])
            branch = branches[index]

            while stack:
                commit = self.__commits.get(stack.pop())

                if commit and commit not in branch:
                    branch.add(commit)

                    for other_index, other_branch in enumerate(branches):
                        if commit not in other_branch: break
                    else:
                        common_ancestors.add(commit)
                        continue

                    stack.update(set(commit.parents))

        return common_ancestors

    def filtered(self, commits):
        filtered = set()
        commits = set(commits)

        while commits:
            commit = commits.pop()

            if commit not in filtered:
                filtered.add(commit)
                commits.update(self.getParents(commit))

        return CommitSet(filtered)

    def without(self, commits):
        """
        Return a copy of this commit set without 'commit' and any ancestors of
        'commit' that don't have other descendants in the commit set.
        """

        pending = set(filter(None, (self.__commits.get(str(commit)) for commit in commits)))
        commits = self.__commits.copy()
        children = self.__children.copy()

        while pending:
            commit = pending.pop()

            del commits[commit]
            if commit in children:
                del children[commit]

            for parent_sha1 in commit.parents:
                if parent_sha1 in commits:
                    children0 = children.get(parent_sha1, set())
                    children0 -= set([commit])
                    if not children0:
                        pending.add(commits[parent_sha1])

        return CommitSet(list(commits.values()))

    def getSubset(self, head):
        assert head in self

        queue = set([head])
        commits = set()

        while queue:
            commit = queue.pop()

            if commit in commits:
                continue

            commits.add(commit)
            queue.update(self.getParents(commit))

        return CommitSet(commits)

    def isAncestorOf(self, ancestor, commit):
        if ancestor == commit:
            return False
        else:
            descendants = self.__children.get(ancestor, set()).copy()
            pending = descendants.copy()

            while pending and not commit in descendants:
                descendant = pending.pop()
                children = self.__children.get(descendant, set()) - descendants

                descendants.update(children)
                pending.update(children)

            return commit in descendants

    @staticmethod
    def fromRange(db, from_commit, to_commit, commits=None):
        repository = to_commit.repository
        commits = set()

        class NotPossible(Exception): pass

        if commits:
            def getCommit(sha1):
                return commits[sha1]
        else:
            def getCommit(sha1):
                return gitutils.Commit.fromSHA1(db, repository, sha1)

        def process(iter_commit):
            while iter_commit != from_commit and iter_commit not in commits:
                commits.add(iter_commit)

                if len(iter_commit.parents) > 1:
                    # A merge commit.  Check if 'from_commit' is an ancestor of
                    # all its parents.  If not, we don't support constructing a
                    # commit-set from this range of commits (not because it is
                    # particularly difficult, but because such a commit-set
                    # would contain "unexpected" merged-in commits.)

                    if from_commit.isAncestorOf(repository.mergebase(iter_commit)):
                        map(process, [getCommit(sha1) for sha1 in iter_commit.parents])
                        return
                    else:
                        raise NotPossible
                elif iter_commit.parents:
                    iter_commit = getCommit(iter_commit.parents[0])
                else:
                    return

        if from_commit == to_commit:
            return CommitSet([to_commit])

        try:
            process(to_commit)
            return CommitSet(commits)
        except NotPossible:
            return None

    @staticmethod
    def fromBranchUpdate(db, current_commits, from_commit, to_commit):
        """Extract the commits to associate with a branch when updated

           Given the commits currently associated with the branch (the set
           |current_commits|), the current head of the branch (the commit
           |from_commit|) and the new head of the branch (the commit
           |to_commit|), calculate and return the set of new commits to
           associate with the branch.

           As a special case, this can be used to calculate the initial set of
           commits to associate with a branch, with an empty |current_commits|
           and the base/tail commit as |from_commit|.

           The rules are that a commit is added if its merge-base with
           |from_commit| is either |from_commit| or some (other) commit in
           |current_commits|.  If a commit is added, then each of its parents
           are considered for addition as well."""

        assert from_commit.isAncestorOf(to_commit)
        assert (not current_commits or
                from_commit in CommitSet(current_commits).getHeads())

        repository = from_commit.repository
        current_commits = set(current_commits)
        new_commits = set()

        def traverse(commit):
            while True:
                # Stop when we reach |from_commit|, a commit in
                # |current_commits|, or a commit we've already processed.
                if commit == from_commit \
                        or commit in current_commits \
                        or commit in new_commits:
                    return

                # Add this commit and consider its parents.
                new_commits.add(commit)

                parents = [gitutils.Commit.fromSHA1(db, repository, sha1)
                           for sha1 in commit.parents]

                if len(parents) == 1:
                    # Optimization: No need to be clever about non-merges.
                    commit = parents[0]
                    continue

                if current_commits:
                    # Updated branch mode: Add (and traverse) any parent whose
                    # merge-base with |from_commit| is already part of the
                    # branch.
                    for parent in parents:
                        base = repository.mergebase([from_commit, parent])
                        if base in current_commits:
                            traverse(parent)
                else:
                    # Created or rebased branch mode: Add (and traverse) the
                    # first parent that is a descendent of |from_commit| (called
                    # |key_parent|) and any subsequent parent that also is, and
                    # whose merge-base with |key_parent| isn't |from_commit|.
                    #
                    # Put differently, we only want to include commits based on
                    # |from_commit|, and only one immediate child of
                    # |from_commit|.  We let the first (included) parent of a
                    # each merge decide which path to take to |from_commit|.
                    key_parent = None
                    for parent in parents:
                        if from_commit.isAncestorOf(parent):
                            if not key_parent:
                                key_parent = parent
                            else:
                                base = repository.mergebase([key_parent, parent])
                                if base == from_commit:
                                    continue
                            traverse(parent)

                break

        traverse(to_commit)

        return CommitSet(new_commits)

    def findEquivalentUpstream(self, db, commit):
        """Find an ancestor of |commit| that is equivalent to an upstream of
           this set

           "Equivalent" in this context means "references the same tree."

           This search can be very expensive if no matching commit is found,
           since we won't know that until we've examined all ancestors."""

        repository = commit.repository
        upstreams_sha1s = self.getFilteredTails(repository)
        valid_trees = set(
            gitutils.Commit.fromSHA1(db, repository, upstream_sha1).tree
            for upstream_sha1 in upstreams_sha1s)

        stack = [commit]
        processed = set()

        while stack:
            commit = stack.pop(0)

            if commit.tree in valid_trees:
                return commit
            elif commit in processed:
                continue

            processed.add(commit)

            stack.extend(gitutils.Commit.fromSHA1(db, repository, parent_sha1)
                         for parent_sha1 in commit.parents
                         if parent_sha1 not in processed)

        return None
