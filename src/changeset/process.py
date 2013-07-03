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
import stat

def joinPaths(dirname, basename):
    return "%s/%s" % (dirname, basename) if dirname else basename

class ChangedPath:
    def __init__(self, path, oldEntry, newEntry):
        self.path = path
        self.oldEntry = oldEntry
        self.newEntry = newEntry

def removedTree(repository, path, sha1):
    changedPaths = []
    for entry in gitutils.Tree.fromSHA1(repository, sha1):
        changedPaths.extend(
            removedEntry(repository, path, entry))
    return changedPaths

def removedEntry(repository, path, entry):
    path = joinPaths(path, entry.name)

    changedPaths = [ChangedPath(path, entry, None)]
    if stat.S_ISDIR(entry.mode):
        changedPaths.extend(
            removedTree(repository, path, entry.sha1))
    return changedPaths

def addedTree(repository, path, sha1):
    changedPaths = []
    for entry in gitutils.Tree.fromSHA1(repository, sha1):
        changedPaths.extend(
            addedEntry(repository, path, entry))
    return changedPaths

def addedEntry(repository, path, entry):
    path = joinPaths(path, entry.name)

    changedPaths = [ChangedPath(path, None, entry)]
    if stat.S_ISDIR(entry.mode):
        changedPaths.extend(
            addedTree(repository, path, entry.sha1))
    return changedPaths

def diffTrees(repository, path, oldTree, newTree):
    oldNames = set(oldTree.keys())
    newNames = set(newTree.keys())

    commonNames = oldNames & newNames
    removedNames = oldNames - commonNames
    addedNames = newNames - commonNames

    changedPaths = []

    for name in removedNames:
        changedPaths.extend(
            removedEntry(repository, joinPaths(path, name), oldTree[name]))
    for name in addedNames:
        changedPaths.extend(
            addedEntry(repository, joinPaths(path, name), newTree[name]))

    for name in commonNames:
        oldEntry = oldTree[name]
        newEntry = newTree[name]

        if oldEntry.sha1 != newEntry.sha1 or oldEntry.mode != newEntry.mode:
            changedPath = joinPaths(path, name)
            changedPaths.append(ChangedPath(changedPath, oldEntry, newEntry))

            commonMode = oldEntry.mode & newEntry.mode
            removedMode = oldEntry.mode - commonMode
            addedMode = newEntry.mode - commonMode

            if stat.S_ISDIR(removedMode):
                changedPaths.extend(
                    removedTree(repository, changedPath, oldEntry.sha1))
            elif stat.S_ISDIR(addedMode):
                changedPaths.extend(
                    addedTree(repository, changedPath, newEntry.sha1))
            elif stat.S_ISDIR(commonMode) and oldEntry.sha1 != newEntry.sha1:
                changedPaths.extend(
                    diffTrees(repository, changedPath,
                              gitutils.Tree.fromSHA1(repository, oldEntry.sha1),
                              gitutils.Tree.fromSHA1(repository, newEntry.sha1)))

    return changedPaths

def diffCommits(repository, commitA, commitB):
    return diffTrees(repository,
                     None,
                     gitutils.Tree.fromSHA1(repository, commitA.tree),
                     gitutils.Tree.fromSHA1(repository, commitB.tree))
