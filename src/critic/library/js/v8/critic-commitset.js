/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2013 Jens Lindström, Opera Software ASA

 Licensed under the Apache License, Version 2.0 (the "License"); you may not
 use this file except in compliance with the License.  You may obtain a copy of
 the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 License for the specific language governing permissions and limitations under
 the License.

*/

"use strict"

function CriticCommitSet(all) {
    Object.defineProperties(this, {
        parents: { value: {} },
        children: { value: {} },
        heads: { value: [] },
        tails: { value: [] },
    })

    this.repository = null

    for (var index = 0; index < all.length; ++index) {
        var commit = all[index]
        if (!this.repository) this.repository = commit.repository
        else if (this.repository.id != commit.repository.id)
            throw CriticError(
                format(
                    "invalid use: commits from multiple repositories in source array ('%s' and '%s')",
                    this.repository.name,
                    commit.repository.name
                )
            )
        if (commit.sha1 in this)
            throw CriticError(
                format(
                    "invalid use: commit %s occurs multiple times in source array",
                    commit.sha1
                )
            )
        Object.defineProperty(this, commit.sha1, { value: commit })
        this.parents[commit.sha1] = []
        this.children[commit.sha1] = []
    }

    for (var index = 0; index < all.length; ++index) {
        var commit = all[index]
        var count = 0

        for (var pindex = 0; pindex < commit.parents.length; ++pindex) {
            var parent = commit.parents[pindex]
            if (parent.sha1 in this) {
                ++count
                this.parents[commit.sha1].push(parent)
            } else if (!(parent.sha1 in this.children))
                this.children[parent.sha1] = []

            this.children[parent.sha1].push(commit)
        }
    }

    for (var index = 0; index < all.length; ++index) {
        var commit = all[index]

        if (this.children[commit.sha1].length == 0) {
            this.heads.push(commit)
            Object.defineProperty(this.heads, commit.sha1, { value: commit })
        }
        if (this.parents[commit.sha1].length < commit.parents.length) {
            for (var index1 = 0; index1 < commit.parents.length; ++index1) {
                var parent = commit.parents[index1]
                if (!(parent.sha1 in this) && !(parent.sha1 in this.tails)) {
                    this.tails.push(parent)
                    Object.defineProperty(this.tails, parent.sha1, {
                        value: parent,
                    })
                }
            }
        }

        Object.freeze(this.parents[commit.sha1])
        Object.freeze(this.children[commit.sha1])
    }

    var added = {}

    for (var index = 0; index < this.heads.length; ++index) {
        var stack = [this.heads[index]]
        var stack_offset = 0

        while (stack_offset < stack.length) {
            var commit = stack[stack_offset++]

            if (commit.sha1 in added) continue

            do {
                var parents = this.parents[commit.sha1]

                this.push(commit)

                added[commit.sha1] = true
                commit = null

                for (var pindex = 0; pindex < parents.length; ++pindex) {
                    var parent = parents[pindex]

                    if (parent.sha1 in added) continue
                    else if (commit === null) commit = parent
                    else stack.push(parent)
                }
            } while (commit)
        }
    }

    var self = this
    var upstreams = null

    function getUpstreams() {
        if (!upstreams) {
            upstreams = self.tails.slice()

            if (upstreams.length > 1) {
                for (var index1 = 0; index1 < upstreams.length; ++index1)
                    for (var index2 = 0; index2 < self.heads.length; ++index2)
                        if (
                            self.heads[index2].isAncestorOf(upstreams[index1])
                        ) {
                            upstreams[index1] = null
                            break
                        }

                for (var index1 = 0; index1 < upstreams.length; ++index1)
                    if (upstreams[index1])
                        for (
                            var index2 = 0;
                            index2 < upstreams.length;
                            ++index2
                        )
                            if (index1 != index2 && upstreams[index2])
                                if (
                                    upstreams[index1].isAncestorOf(
                                        upstreams[index2]
                                    )
                                ) {
                                    upstreams[index1] = null
                                    break
                                }

                upstreams = upstreams.filter(function(commit) {
                    return commit !== null
                })
            }

            Object.freeze(upstreams)
        }

        return upstreams
    }

    Object.defineProperty(this, "upstreams", { get: getUpstreams })

    Object.freeze(this.parents)
    Object.freeze(this.children)
    Object.freeze(this.heads)
    Object.freeze(this.tails)
    Object.freeze(this)
}

var properties = {
    restrict: {
        value: function(heads, tails) {
            var reachable = []
            var self = this

            var exclude = {}
            if (tails)
                for (var index = 0; index < tails.length; ++index) {
                    var tail = tails[index]

                    if (!(tail.sha1 in this) && !(tail.sha1 in this.tails))
                        throw CriticError(
                            "CommitSet.restrict: invalid tail commits; not member or tail of commit-set"
                        )

                    exclude[tail.sha1] = true
                }

            function add(commit) {
                if (!(commit.sha1 in reachable) && !(commit.sha1 in exclude)) {
                    reachable.push(commit)
                    reachable[commit.sha1] = commit

                    var parents = self.parents[commit.sha1]
                    for (var index = 0; index < parents.length; ++index)
                        add(parents[index])
                }
            }

            for (var index = 0; index < heads.length; ++index)
                if (heads[index].sha1 in this) add(heads[index])

            return new CriticCommitSet(reachable)
        },
        writable: true,
        configurable: true,
    },

    without: {
        value: function(commits) {
            var remaining = []

            for (var index = 0; index < this.length; ++index)
                if (!(this[index].sha1 in commits)) remaining.push(this[index])

            return new CriticCommitSet(remaining)
        },
        writable: true,
        configurable: true,
    },

    getChangeset: {
        value: function(data) {
            if (this.length == 0) return null

            if (this.heads.length != 1)
                throw CriticError(
                    format(
                        "commit-set has multiple heads: %d",
                        this.heads.length
                    )
                )
            if (this.upstreams.length != 1)
                throw CriticError("commit-set has multiple upstreams")

            data = data || {}

            data.parent = this.upstreams[0]
            data.child = this.heads[0]
            data.commits = this

            return this.repository.getChangeset(data)
        },
        writable: true,
        configurable: true,
    },
}

CriticCommitSet.prototype = Object.create(Array.prototype, properties)
