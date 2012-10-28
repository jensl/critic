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

class CommitSet:
    def __init__(self, commits):
        self.__commits = dict([(str(commit), commit) for commit in commits])

        parents = set()
        tails = set()

        for commit in self.__commits.values():
            parents.update([parent for parent in commit.parents])

        commit_set = set(self.__commits.values())

        # Heads: commits that aren't the parent of a commit in the set.
        self.__heads = commit_set - parents

        # Tails: parent commits not included in the set.
        self.__tails = parents - commit_set

    def getHeads(self):
        return self.__heads

    def getTails(self):
        return self.__tails

    def getTailsFrom(self, commit):
        """Return a set containing the each tail commit of the set of commits that are
ancestors of 'commit' and that are members of this commit set.  A tail commit of
a set is a commit that is not a member of the set but that is a parent of a
commit that is a member of the set."""

        if commit not in self.__commits: raise Exception, "invalid use"

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
                    else: tails.add(parent)

        return tails
