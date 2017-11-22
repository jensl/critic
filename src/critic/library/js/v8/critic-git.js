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

var RE_LSTREE_LINE = /^([0-9]{6}) (blob|tree|commit) ([0-9a-f]{40})  *([0-9]+|-)\t(.*)$/

var all_repositories = []

function GitObject(sha1, type, size, data) {
    this.sha1 = sha1
    this.type = type
    this.size = size
    this.data = data

    Object.freeze(this)
}

function CriticCommitFileVersion(commit, path_or_id, data) {
    var path

    if (typeof path_or_id == "number") path = CriticFile.find(path_or_id).path
    else path = path_or_id

    var match = /((?:[^\/]+\/)*[^\/]+)/.exec(path)
    if (!match) throw CriticError(format("invalid path: %s", path))
    path = match[1]

    var match = /^(?:(.*)\/)?([^/]+)$/.exec(path)
    var dirname = match[1] || ""
    var basename = match[2]

    var line = commit.repository.run(
        "ls-tree",
        "--long",
        format("%s:%s", commit.sha1, dirname),
        basename
    )

    try {
        match = RE_LSTREE_LINE.exec(line.trim())
    } catch (e) {
        throw new TypeError(Object.prototype.toString.apply(line))
    }

    if (!match)
        throw CriticError(format("path doesn't exist in commit: '%s'", path))

    var mode = match[1]
    var type = match[2]
    var sha1 = match[3]
    var size = match[4]
    var name = match[5]

    if (type != "blob")
        throw CriticError(format("path names a directory: '%s'", path))

    CriticFileVersion.call(
        this,
        commit.repository,
        path,
        mode,
        size,
        sha1,
        data
    )

    this.commit = commit

    Object.freeze(this)
}

CriticCommitFileVersion.prototype = Object.create(CriticFileVersion.prototype)

function CriticCommitDirectory(commit, path) {
    if (path == "/") path = ""
    else {
        var match = /^((?:[^\/]+\/)*[^\/]+)/.exec(path)
        if (!match) throw CriticError(format("invalid path: %s", path))
        path = match[1]
    }

    var data = commit.repository.run(
        "ls-tree",
        "--long",
        format("%s:%s", commit.sha1, path)
    )
    var lines = data.trim().split("\n")
    var low_directories = [],
        low_files = []

    for (var index = 0; index < lines.length; ++index) {
        var match = RE_LSTREE_LINE.exec(lines[index])

        if (!match) throw Error(format("Unexpected line: %r", lines[index]))

        var mode = match[1]
        var type = match[2]
        var sha1 = match[3]
        var size = match[4]
        var name = match[5]

        if (type == "blob") low_files.push([mode, sha1, size, name])
        else if (type == "tree") low_directories.push(name)
    }

    this.path = path || "/"
    this.commit = commit

    var self = this
    var parent
    var directories
    var files

    function getParent() {
        if (parent === void 0) {
            var match = /(.+)\/[^\/]+/.exec(self.path)
            if (!match) parent = null
            else parent = new CriticCommitDirectory(self.commit, match[1])
        }

        return parent
    }

    function getDirectories() {
        if (!directories) {
            directories = []

            for (var index = 0; index < low_directories.length; ++index) {
                var path = low_directories[index]
                if (self.path != "/") path = format("%s/%s", self.path, path)
                directories.push(new CriticCommitDirectory(self.commit, path))
            }
        }

        return directories
    }

    function getFiles() {
        if (!files) {
            files = []

            for (var index = 0; index < low_files.length; ++index) {
                var path = low_files[index][3]
                if (self.path != "/") path = format("%s/%s", self.path, path)
                files.push(new CriticCommitFileVersion(self.commit, path))
            }
        }

        return files
    }

    Object.defineProperties(this, {
        parent: { get: getParent, enumerable: true },
        directories: { get: getDirectories, enumerable: true },
        files: { get: getFiles, enumerable: true },
    })
    Object.freeze(this)
}

function runGitCommand(path, args) {
    var env

    if (typeof args[args.length - 1] == "object") env = args.pop()
    else env = {}

    env["REMOTE_USER"] = global.user.name

    var stdin

    if ("stdin" in env) {
        stdin = env["stdin"]
        delete env["stdin"]
    }

    var argv = [git_executable]

    ;[].push.apply(argv, args)

    var process = new OS.Process(git_executable, {
        argv: argv,
        cwd: path,
        environ: env,
    })

    if (stdin !== void 0) process.stdin = new IO.MemoryFile(stdin, "r")

    process.stdout = new IO.MemoryFile()
    process.stderr = new IO.MemoryFile()

    try {
        process.run()
    } catch (error) {
        var message

        if (process.exitStatus !== null)
            message = format("Git exited with status %d", process.exitStatus)
        else
            message = format(
                "Git terminated by signal %d",
                process.terminationSignal
            )

        var stderr = process.stderr.value.decode()

        if (stderr.trim()) message += format("\n%s", stderr)

        throw CriticError(message)
    }

    return process.stdout.value.decode()
}

function CriticRepository(name_or_id) {
    var repository_id

    if (typeof name_or_id == "number") repository_id = name_or_id
    else {
        var result = db.execute(
            "SELECT id FROM repositories WHERE name=%s",
            name_or_id
        )

        if (result.length) repository_id = result[0].id
        else throw CriticError(format("%s: no such repository", name_or_id))
    }

    for (var index = 0; index < all_repositories.length; ++index)
        if (all_repositories[index].id == repository_id)
            return all_repositories[index]

    var result = db.execute(
        "SELECT name, path, parent FROM repositories WHERE id=%d",
        repository_id
    )[0]

    if (!result)
        throw CriticError(format("%s: invalid repository ID", repository_id))

    var command = {
        name: "check-repository-access",
        data: {
            repository_id: repository_id,
        },
    }

    this.access = JSON.parse(executeCLI([command])[0])

    if (!this.access.read) throw CriticError(format("access denied"))

    this.id = repository_id
    this.name = result.name
    this.path = result.path

    var self = this
    var catfile = null,
        catfile_in,
        catfile_out,
        catfile_buffer
    var filters = null

    this.fetch = function(sha1) {
        if (!catfile) {
            var stdin = new IO.Pipe()
            var stdout = new IO.Pipe()
            var argv = [git_executable, "cat-file", "--batch"]

            catfile = new OS.Process(git_executable, {
                argv: argv,
                cwd: self.path,
            })
            catfile.stdin = stdin.input
            catfile.stdout = stdout.output
            catfile.stderr = new IO.MemoryFile()

            catfile_in = stdin.output
            catfile_in.setCloseOnExec(true)
            catfile_out = stdout.input
            catfile_buffer = new IO.Buffered(catfile_out)

            catfile.start()
        }

        try {
            catfile_in.write(format("%s\n", sha1))

            var line = catfile_buffer.readln()

            if (!line)
                throw CriticError(
                    format("failed to fetch %s: empty response", sha1)
                )

            var match = /^([0-9a-f]{40}) (commit|tree|blob|tag) (\d+)$/.exec(
                line
            )

            if (!match || match[1] != sha1)
                throw CriticError(
                    format(
                        "failed to fetch %s: invalid response: %s",
                        sha1,
                        JSON.stringify(line)
                    )
                )

            var type = match[2]
            var size = parseInt(match[3])
            var data = catfile_buffer.read(size)

            catfile_buffer.read(1)

            return new GitObject(sha1, type, size, data)
        } catch (error) {
            this.shutdown()
            throw error
        }
    }

    this.shutdown = function() {
        if (catfile) {
            try {
                catfile.kill(9)
                catfile.wait()
            } catch (e) {}
            try {
                catfile_in.close()
            } catch (e) {}
            try {
                catfile_out.close()
            } catch (e) {}

            catfile = catfile_in = catfile_out = catfile_buffer = null
        }
    }

    all_repositories.push(this)

    function getFilters() {
        var users = {}

        function getUser(name_or_id) {
            var user = users[name_or_id]

            if (user) return user
            else user = new CriticUser(name_or_id)

            return (users[user.id] = users[user.name] = user)
        }

        if (!filters) {
            filters = []

            Object.defineProperties(filters, {
                users: { value: {} },
                paths: { value: {} },
            })

            var result = db.execute(
                "SELECT uid, path, type, delegate FROM filters WHERE repository=%d",
                self.id
            )

            for (var index = 0; index < result.length; ++index) {
                var row = result[index]
                var user = getUser(row.uid)
                var path = row.path
                var delegates = []

                if (row.delegate)
                    row.delegate.split(",").forEach(function(name) {
                        try {
                            delegates.push(getUser(name))
                        } catch (error) {
                            /* Ignore invalid user names in the 'delegate' column. */
                        }
                    })

                var filter = Object.freeze({
                    user: user,
                    path: path,
                    type: row.type,
                    delegates: delegates,
                })

                filters.push(filter)

                ;(
                    filters.users[user.name] || (filters.users[user.name] = [])
                ).push(filter)
                ;(filters.paths[path] || (filters.paths[path] = [])).push(
                    filter
                )
            }

            for (var name in filters.users) Object.freeze(filters.users[name])
            Object.freeze(filters.users)

            for (var path in filters.paths) Object.freeze(filters.paths[path])
            Object.freeze(filters.paths)

            Object.freeze(filters)
        }

        return filters
    }

    Object.defineProperties(this, {
        filters: { get: getFilters, enumerable: true },
    })
    Object.freeze(this)
}

function GitUserTime(fullname, email, utc) {
    this.fullname = fullname
    this.email = email
    this.time = new Date(parseInt(utc) * 1000)

    var self = this
    var user = null

    function getUser() {
        if (!user)
            try {
                user = new CriticUser({ email: self.email })
            } catch (error) {
                return null
            }

        return user
    }

    Object.defineProperty(this, "user", { get: getUser, enumerable: true })
    Object.freeze(this)
}

GitUserTime.prototype.toString = function() {
    return format("%s <%s> at %s", this.fullname, this.email, this.time)
}

function CriticCommit(repository, sha1) {
    var object = repository.fetch(sha1)

    while (object.type == "tag") {
        sha1 = object.data
            .decode()
            .split("\n")[0]
            .split(" ")[1]
        object = repository.fetch(sha1)
    }

    if (object.type != "commit") throw CriticError("not a commit")

    var text = object.data.decode()
    var tree,
        author,
        committer,
        parents_sha1 = [],
        message

    while (true) {
        var line_length = text.indexOf("\n")

        if (line_length == 0) {
            message = text.substring(1)
            break
        } else {
            var line = text.substring(0, line_length),
                match

            if ((match = /^tree ([0-9a-f]{40})$/i.exec(line))) tree = match[1]
            else if ((match = /^parent ([0-9a-f]{40})$/i.exec(line)))
                parents_sha1.push(match[1])
            else if (
                (match = /^author (.+?) <([^>]+)> (\d+) ([-+]\d+)$/i.exec(line))
            )
                author = new GitUserTime(match[1], match[2], match[3])
            else if (
                (match = /^committer (.+?) <([^>]+)> (\d+) ([-+]\d+)$/i.exec(
                    line
                ))
            )
                committer = new GitUserTime(match[1], match[2], match[3])

            text = text.substring(line_length + 1)
        }
    }

    var self = this
    var commit_id = null
    var parents = null

    function getId() {
        if (commit_id === null) {
            var result = db.execute(
                "SELECT id FROM commits WHERE sha1=%s",
                sha1
            )

            if (result.length) commit_id = result[0].id
            else
                throw CommitError(
                    format("%s: commit not registered in the database", sha1)
                )
        }

        return commit_id
    }

    function getParents() {
        if (parents === null)
            parents = parents_sha1.map(function(sha1) {
                return new CriticCommit(repository, sha1)
            })

        return parents
    }

    function getSummary() {
        var match = /^(fixup|squash)! [^\n]+\n+([^\n]+)/.exec(message)
        if (match) return format("[%s] %s", match[1], match[2])
        else return /^[^\n]*/.exec(message)[0]
    }

    function getShort() {
        return repository.revparse(self.sha1, true)
    }

    Object.defineProperties(this, {
        id: { get: getId, enumerable: true },
        parents: { get: getParents, enumerable: true },
        summary: { get: getSummary, enumerable: true },
        short: { get: getShort, enumerable: true },
    })

    this.repository = repository
    this.sha1 = sha1
    this.tree = tree
    this.author = author
    this.committer = committer
    this.message = message

    Object.freeze(this)
}

Object.defineProperties(CriticCommit.prototype, {
    toString: {
        value: function() {
            return format("%s: %s", this.sha1.substring(0, 8), this.summary)
        },
        writable: true,
        configurable: true,
    },

    getDirectory: {
        value: function(path) {
            return new CriticCommitDirectory(this, path)
        },
        writable: true,
        configurable: true,
    },

    getFile: {
        value: function(path, data) {
            return new CriticCommitFileVersion(this, path, data)
        },
        writable: true,
        configurable: true,
    },

    isAncestorOf: {
        value: function(other) {
            if (!(this instanceof CriticCommit))
                throw CriticError("invalid this object: expected Commit object")
            if (!(other instanceof CriticCommit))
                throw CriticError(
                    "invalid 'other' argument: expected Commit object"
                )
            if (this.repository.id != other.repository.id) return false
            else if (this.sha1 == other.sha1) return true
            else
                return (
                    this.repository
                        .run("merge-base", this.sha1, other.sha1)
                        .trim() == this.sha1
                )
        },
        writable: true,
        configurable: true,
    },
})

CriticRepository.prototype.run = function() {
    return runGitCommand(this.path, [].slice.apply(arguments))
}
CriticRepository.prototype.run.supportsInput = true

CriticRepository.prototype.revparse = function(ref, use_short) {
    if (!ref || typeof ref != "string")
        throw CriticError("invalid ref argument: expected non-empty string")
    else {
        var short = "--short=40"
        if (use_short)
            if (use_short === true) short = "--short"
            else short = format("--short=%d", use_short)
        return this.run("rev-parse", "--verify", "--quiet", short, ref).trim()
    }
}

CriticRepository.prototype.revlist = function(data) {
    var args = ["rev-list"]

    if (data.options) {
        ;[].push.apply(
            args,
            [].map.call(data.options, function(option) {
                if (!/-[a-z]|--[a-z-]+(?:=.*)/.test(option))
                    throw CriticError("invalid option: " + option)
                return option
            })
        )
    }

    if (data.included) {
        ;[].push.apply(args, [].map.call(data.included, String))

        if (data.excluded)
            [].push.apply(
                args,
                [].map.call(data.excluded, function(ref) {
                    return "^" + String(ref)
                })
            )
    } else if (data.range) {
        var range = String(data.range)
        if (range.match(/\.\.\.?/g).length != 1)
            throw CriticError("invalid range")
        args.push(range)
    } else
        throw CriticError(
            "invalid argument: data.included or data.range must be specified"
        )

    return this.run
        .apply(this, args)
        .trim()
        .split("\n")
}

CriticRepository.prototype.getCommit = function(ref_or_id) {
    var sha1

    if (typeof ref_or_id == "number")
        sha1 = db.execute("SELECT sha1 FROM commits WHERE id=%d", ref_or_id)[0]
            .sha1
    else sha1 = this.revparse(ref_or_id)

    return new CriticCommit(this, sha1)
}

CriticRepository.prototype.getBranch = function(name) {
    return new CriticBranch({ repository: this, name: name })
}

function createChangeset(repository, type, parent, child) {
    var socket = new IO.Socket("unix", "stream")
    var request = {
        repository_name: repository.name,
        changeset_type: type,
    }

    switch (type) {
        case "direct":
        case "merge":
            request.child_sha1 = child.sha1
            break
        case "custom":
        case "conflicts":
            request.parent_sha1 = parent.sha1
            request.child_sha1 = child.sha1
    }

    socket.connect(IO.SocketAddress.unix(changeset_address))
    socket.send(JSON.stringify([request]))
    socket.shutdown("write")

    var result = ""

    while (true) {
        var data = socket.recv(4096)
        if (data === null) break
        result += data.decode()
    }

    result = JSON.parse(result)

    if (
        !(result instanceof Array) ||
        result.length != 1 ||
        "error" in result[0]
    )
        throw CriticError(format("failed to create changeset!"))
}

CriticRepository.prototype.getChangeset = function(data) {
    var data_argument = data

    if (typeof data == "number") data = { id: data }
    else if (typeof data.id == "number") {
        data = { id: data.id }
        if (data_argument.parent) data.parent = data_argument.parent
        if (data_argument.child) data.child = data_argument.child
        if (data_argument.commit) data.commit = data_argument.commit
    } else {
        var commit, parent, child, type

        if (data instanceof CriticCommit) commit = data
        else if (data.commit)
            if (data.commit instanceof CriticCommit) commit = data.commit
            else commit = this.getCommit(data.commit)

        if (commit) {
            if (commit.parents.length != 1)
                throw CriticError(
                    "invalid use; commit is a merge, use getMergeChangeset() instead"
                )

            child = commit
            parent = commit.parents[0]
            type = "direct"
        } else {
            if (data.parent instanceof CriticCommit) parent = data.parent
            else parent = this.getCommit(data.parent)

            if (data.child instanceof CriticCommit) child = data.child
            else child = this.getCommit(data.child)

            if (
                child.parents.length == 1 &&
                child.parents[0].sha1 == parent.sha1
            )
                type = "direct"
            else type = "custom"
        }

        for (var attempt = 0; attempt < 2; ++attempt) {
            var result = db.execute(
                "SELECT id FROM changesets WHERE parent=%d AND child=%d AND type IN ('direct', 'custom')",
                parent.id,
                child.id
            )

            if (result.length) {
                data = { id: result[0].id, parent: parent, child: child }
                break
            } else if (attempt == 0) createChangeset(this, type, parent, child)
        }

        if (attempt == 2)
            throw CriticError(
                "mysterious error creating/finding cached changeset"
            )
    }

    if (typeof data_argument == "object")
        for (var name in data_argument)
            switch (name) {
                case "id":
                case "commit":
                case "child":
                case "parent":
                    break

                default:
                    data[name] = data_argument[name]
            }

    return new CriticChangeset(this, data)
}

CriticRepository.prototype.getMergeChangeset = function(commit, data) {
    var commit

    data = data || {}

    if (!(commit instanceof CriticCommit)) commit = this.getCommit(commit)

    if (commit.parents.length < 2)
        throw CriticError(
            format("invalid use; %s is not a merge commit", commit.sha1)
        )

    for (var attempt = 0; attempt < 2; ++attempt) {
        var result = db.execute(
            "SELECT id FROM changesets WHERE child=%d AND type='merge'",
            commit.id
        )

        if (result.length) {
            var changesets = []

            for (var index = 0; index < result.length; ++index) {
                data.id = result[index].id
                data.child = commit

                changesets.push(new CriticChangeset(this, data))
            }

            return new CriticMergeChangeset(changesets)
        } else if (attempt == 0) createChangeset(this, "merge", null, commit)
    }

    throw CriticError("mysterious error creating/finding cached changeset")
}

function CriticRepositoryWorkCopy(repository, branch) {
    if (
        !repository_work_copy_path ||
        !IO.File.isDirectory(repository_work_copy_path) ||
        global.user.id === null
    )
        throw CriticError("operation not available")

    var name = format(
        "%s/%d/%s",
        global.user.name,
        extension_id,
        repository.name
    )
    var path = repository_work_copy_path + "/" + name

    this.repository = repository
    this.path = path

    if (IO.File.isDirectory(path)) {
        this.run("clean", "-d", "-x", "-f", "-f")
        this.run("reset", "--hard")

        if (branch) {
            this.run("fetch", "origin", "refs/heads/" + branch)
            this.run("checkout", "-q", "FETCH_HEAD")
            try {
                this.run("branch", "-D", branch)
            } catch (e) {}
            this.run("checkout", "-q", "-b", branch)
        } else {
            try {
                var ref = repository
                    .run("symblic-ref", "--quiet", "HEAD")
                    .trim()
                this.run("fetch", "origin", ref)
                ref = "FETCH_HEAD"
            } catch (error) {
                ref = repository.run("rev-parse", "HEAD").trim()
            }

            this.run("checkout", "-q", ref)
        }

        IO.File.utimes(path)
    } else {
        var argv = [git_executable, "clone"]

        if (branch) argv.push("-b", branch)

        argv.push(repository.path, name)

        var process = new OS.Process(git_executable, {
            argv: argv,
            cwd: repository_work_copy_path,
        })

        return process.call()
    }
}

CriticRepositoryWorkCopy.prototype.run = function() {
    return runGitCommand(this.path, [].slice.apply(arguments))
}
CriticRepositoryWorkCopy.prototype.run.supportsInput = true

CriticRepository.prototype.getWorkCopy = function() {
    return new CriticRepositoryWorkCopy(this)
}

CriticRepository.prototype.startFiltersTransaction = function() {
    return new CriticFiltersTransaction(this)
}
