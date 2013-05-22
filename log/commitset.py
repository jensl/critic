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

        return CommitSet(commits.values())

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
