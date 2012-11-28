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

from subprocess import Popen as process, PIPE, STDOUT
import re
import time
import atexit
from traceback import print_exc, format_exc
from os import kill, environ
import threading

import base
import configuration
from utf8utils import convertUTF8
import htmlutils
import os.path
import shutil
import os
import atexit
import stat

re_author_committer = re.compile("(.*) <(.*)> ([0-9]+ [-+][0-9]+)")
re_sha1 = re.compile("^[A-Za-z0-9]{40}$")

REPOSITORY_REPLAY_PATH_FORMAT = os.path.join(configuration.paths.DATA_DIR,
                                             "temporary",
                                             "%(repository.name)s",
                                             "%(user.name)s_%(commit.sha1)s_%(time)s")

class GitError(Exception):
    def __init__(self, message, sha1=None, ref=None, repository=None):
        super(GitError, self).__init__(message)
        self.sha1 = sha1
        self.ref = ref
        self.repository = repository

class GitObject:
    def __init__(self, sha1, type, size, data):
        self.sha1 = sha1
        self.type = type
        self.size = size
        self.data = data

    def __getitem__(self, index):
        if index == 0: return self.type
        elif index == 1: return self.size
        elif index == 2: return self.data
        raise IndexError, "GitObject index out of range: %d" % index

class NoSuchRepository(base.Error):
    def __init__(self, value):
        super(NoSuchRepository, self).__init__("No such repository: %s" % str(value))
        self.value = value

class Repository:
    class FromParameter:
        def __init__(self, db): self.db = db
        def __call__(self, value): return Repository.fromParameter(self.db, value)

    def __init__(self, db=None, repository_id=None, parent=None, main_branch_id=None, name=None, path=None, relay=None):
        assert path

        self.id = repository_id
        self.name = name
        self.path = path
        self.relay = relay
        self.parent = parent

        self.__main_branch = None
        self.__main_branch_id = main_branch_id
        self.__batch = None
        self.__batchCheck = None
        self.__cacheBlobs = False
        self.__cacheDisabled = False

        if db:
            self.__db = db
            db.storage["Repository"][repository_id] = self
            db.storage["Repository"][name] = self
            db.atexit(self.__terminate)
        else:
            self.__db = None
            atexit.register(self.__terminate)

        self.__startBatch()

    def __str__(self):
        return "%s:%s" % (configuration.base.HOSTNAME, self.path)

    def enableBlobCache(self):
        assert self.__db
        self.__cacheBlobs = True

    def disableCache(self):
        self.__cacheDisabled = True

    def hasMainBranch(self):
        return self.__main_branch_id is not None

    def getMainBranch(self, db):
        import dbutils
        if not self.__main_branch:
            if self.__main_branch_id is not None:
                self.__main_branch = dbutils.Branch.fromId(db, self.__main_branch_id, load_commits=False)
        return self.__main_branch

    @staticmethod
    def fromId(db, repository_id):
        if repository_id in db.storage["Repository"]:
            return db.storage["Repository"][repository_id]
        else:
            cursor = db.cursor()
            cursor.execute("SELECT parent, branch, name, path, relay FROM repositories WHERE id=%s", (repository_id,))
            try:
                parent_id, main_branch_id, name, path, relay = cursor.fetchone()
                parent = None if parent_id is None else Repository.fromId(db, parent_id)
                return Repository(db, repository_id=repository_id, parent=parent, main_branch_id=main_branch_id, name=name, path=path, relay=relay)
            except:
                return None

    @staticmethod
    def fromName(db, name):
        if name in db.storage["Repository"]:
            return db.storage["Repository"][name]
        else:
            cursor = db.cursor()
            cursor.execute("SELECT id FROM repositories WHERE name=%s", (name,))
            try: return Repository.fromId(db, cursor.fetchone()[0])
            except: return None

    @staticmethod
    def fromParameter(db, parameter):
        try: repository = Repository.fromId(db, int(parameter))
        except: repository = Repository.fromName(db, parameter)
        if repository: return repository
        else: raise NoSuchRepository, parameter

    @staticmethod
    def fromSHA1(db, sha1):
        cursor = db.cursor()
        cursor.execute("SELECT id FROM repositories ORDER BY id ASC")
        for (repository_id,) in cursor:
            repository = Repository.fromId(db, repository_id)
            if repository.iscommit(sha1): return repository

    def __terminate(self, db=None):
        if self.__batch:
            try: kill(self.__batch.pid, 9)
            except: pass
            try: self.__batch.wait()
            except: pass
            self.__batch = None
        if self.__batchCheck:
            try: kill(self.__batchCheck.pid, 9)
            except: pass
            try: self.__batchCheck.wait()
            except: pass
            self.__batchCheck = None

    def __startBatch(self):
        if self.__batch is None:
            self.__batch = process([configuration.executables.GIT, 'cat-file', '--batch'],
                                   stdin=PIPE, stdout=PIPE, stderr=STDOUT, cwd=self.path)

    def __startBatchCheck(self):
        if self.__batchCheck is None:
            self.__batchCheck = process([configuration.executables.GIT, 'cat-file', '--batch-check'],
                                        stdin=PIPE, stdout=PIPE, stderr=STDOUT, cwd=self.path)

    def getJS(self):
        return "var repository = critic.repository = new Repository(%d, %s, %s);" % (self.id, htmlutils.jsify(self.name), htmlutils.jsify(self.path))

    def getModuleRepository(self, db, commit, path):
        tree = Tree.fromPath(commit, "/")
        source = self.fetch(tree[".gitmodules"].sha1).data
        lines = iter(source.splitlines())

        for line in lines:
            if line == ('[submodule "%s"]' % path): break
        else: return None

        for line in lines:
            line = line.strip()

            if not line or line[0] == "#": continue
            elif line[0] == "[": return None

            key, value = map(str.strip, line.split("="))

            if key == "url":
                path = os.path.abspath(os.path.join(self.path, value))

                cursor = db.cursor()
                cursor.execute("SELECT id FROM repositories WHERE path=%s", (path,))

                return Repository.fromId(db, cursor.fetchone()[0])
        else:
            return None

    def fetch(self, sha1, fetchData=True):
        if self.__db:
            cache = self.__db.storage["Repository"]
            cached_object = cache.get("object:" + sha1)
            if cached_object:
                self.__db.recordProfiling("fetch: " + cached_object.type + " (cached)", 0)
                return cached_object

        before = time.time()

        if fetchData:
            self.__startBatch()
            stdin, stdout = self.__batch.stdin, self.__batch.stdout
        else:
            self.__startBatchCheck()
            stdin, stdout = self.__batchCheck.stdin, self.__batchCheck.stdout

        stdin.write(sha1 + '\n')
        line = stdout.readline()

        if line == ("%s missing\n" % sha1):
            raise GitError("%s missing from %s" % (sha1[:8], self.path), sha1=sha1, repository=self)

        try: sha1, type, size = line.split()
        except: raise GitError("unexpected output from 'git cat-file --batch': %s" % line)

        size = int(size)

        if fetchData:
            data = stdout.read(size)
            stdout.read(1)
        else:
            data = None

        git_object = GitObject(sha1, type, size, data)

        after = time.time()

        if not self.__cacheDisabled and (type != "blob" or self.__cacheBlobs):
            cache["object:" + sha1] = git_object

        if self.__db:
            self.__db.recordProfiling("fetch: " + type, after - before)

        return git_object

    def run(self, command, *arguments, **kwargs):
        return self.runCustom(self.path, command, *arguments, **kwargs)

    def runRelay(self, command, *arguments, **kwargs):
        if not os.path.isdir(self.relay):
            try: os.makedirs(os.path.dirname(self.relay))
            except: pass

            self.runCustom(os.path.dirname(self.relay), "clone", "--bare", self.path, os.path.basename(self.relay))

        return self.runCustom(self.relay, command, *arguments, **kwargs)

    def runCustom(self, cwd, command, *arguments, **kwargs):
        argv = [configuration.executables.GIT, command]
        argv.extend(arguments)
        stdin_data = kwargs.get("input")
        if stdin_data is None: stdin = None
        else: stdin = PIPE
        env = {}
        env.update(environ)
        env.update(kwargs.get("env", {}))
        if "GIT_DIR" in env: del env["GIT_DIR"]
        git = process(argv, stdin=stdin, stdout=PIPE, stderr=PIPE, cwd=cwd, env=env)
        stdout, stderr = git.communicate(stdin_data)
        if kwargs.get("check_errors", True):
            if git.returncode == 0:
                if kwargs.get("include_stderr", False):
                    return stdout + stderr
                else:
                    return stdout
            else: raise Exception, "'%s' failed: %s (in %s)" % (" ".join(argv), stderr.strip(), cwd)
        else:
            return git.returncode, stdout, stderr

    def branch(self, name, startpoint):
        git = process([configuration.executables.GIT, 'branch', name, startpoint],
                      stdout=PIPE, stderr=PIPE, cwd=self.path)
        stdout, stderr = git.communicate()
        if git.returncode != 0: raise Exception, stderr

    def mergebase(self, commit_or_commits, db=None):
        if db and isinstance(commit_or_commits, Commit):
            cursor = db.cursor()
            cursor.execute("SELECT mergebase FROM mergebases WHERE commit=%s", (commit_or_commits.getId(db),))
            try:
                return cursor.fetchone()[0]
            except:
                result = self.mergebase(commit_or_commits)
                cursor.execute("INSERT INTO mergebases (commit, mergebase) VALUES (%s, %s)", (commit_or_commits.getId(db), result))
                return result

        try: sha1s = commit_or_commits.parents
        except: sha1s = map(str, commit_or_commits)

        assert len(sha1s) >= 2

        git = process([configuration.executables.GIT, 'merge-base'] + sha1s,
                      stdout=PIPE, stderr=PIPE, cwd=self.path)
        stdout, stderr = git.communicate()
        if git.returncode == 0: return stdout.strip()
        else: raise Exception, "'git merge-base' failed: %s" % stderr.strip()

    def getCommonAncestor(self, commit_or_commits):
        try: sha1s = commit_or_commits.parents
        except: sha1s = list(commit_or_commits)

        assert len(sha1s) >= 2

        mergebases = [self.mergebase([sha1s[0], sha1]) for sha1 in sha1s[1:]]

        if len(mergebases) == 1: return mergebases[0]
        else: return self.getCommonAncestor(mergebases)

    def revparse(self, name):
        git = process([configuration.executables.GIT, 'rev-parse', '--verify', '--quiet', name],
                      stdout=PIPE, stderr=PIPE, cwd=self.path)
        stdout, stderr = git.communicate()
        if git.returncode == 0: return stdout.strip()
        else: raise GitError("'git rev-parse' failed: %s" % stderr.strip(), ref=name, repository=self)

    def revlist(self, included, excluded, *args, **kwargs):
        args = list(args)
        args.extend([str(ref) for ref in included])
        args.extend(['^' + str(ref) for ref in excluded])
        if "paths" in kwargs:
            args.append("--")
            args.extend(kwargs["paths"])
        return self.run('rev-list', *args).splitlines()

    def iscommit(self, name):
        git = process([configuration.executables.GIT, 'cat-file', '-t', name],
                      stdout=PIPE, stderr=PIPE, cwd=self.path)
        stdout, stderr = git.communicate()
        if git.returncode == 0: return stdout.strip() == "commit"
        else: return False

    def keepalive(self, commit):
        self.run('update-ref', 'refs/keepalive/%s' % str(commit), str(commit))

    def replaymerge(self, db, user, commit):
        now = time.time()

        timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime(now)) + ("_%04d" % ((now * 10000) % 10000))

        path = REPOSITORY_REPLAY_PATH_FORMAT % { "repository.name": self.name,
                                                 "user.name": user.name,
                                                 "commit.sha1": commit.sha1,
                                                 "time": timestamp }

        if os.path.exists(path):
            raise Exception, "%s: path already exists!?!" % path

        if not os.path.exists(os.path.dirname(path)):
            old_umask = os.umask(0002)
            os.makedirs(os.path.dirname(path))
            os.umask(old_umask)

        self.runCustom(os.path.dirname(path), "clone", "--quiet", self.path, os.path.basename(path))

        try:
            # Then fetch everything from the main repository into the work copy.
            self.keepalive(commit)
            self.runCustom(path, 'fetch', 'origin', 'refs/keepalive/%s:refs/heads/merge' % commit.sha1)

            parent_sha1s = commit.parents

            # Create and check out a branch at first parent.
            self.runCustom(path, 'checkout', '-b', 'replay', parent_sha1s[0])

            # Then perform the merge with the other parents.
            returncode, stdout, stderr = self.runCustom(path, "merge", *parent_sha1s[1:], **{ "check_errors": False })

            # If the merge produced conflicts, just stage and commit them:
            if returncode != 0:
                # Then stage and commit the result, with conflict markers and all.
                self.runCustom(path, "commit", "--all", "--message=replay of merge that produced %s" % commit.sha1)

            # Then push the branch to the main repository.
            self.runCustom(path, 'push', 'origin', 'refs/heads/replay:refs/replays/%s' % commit.sha1)

            # Finally, return the resulting commit.
            return Commit.fromSHA1(db, self, self.run('rev-parse', 'refs/replays/%s' % commit.sha1).strip())
        finally:
            # Delete the temporary repository.
            shutil.rmtree(path)

    def getDefaultRemote(self, db):
        cursor = db.cursor()
        cursor.execute("""SELECT remote
                            FROM trackedbranches
                           WHERE repository=%s
                             AND local_name IN ('*', 'master')
                        ORDER BY local_name
                           LIMIT 1""",
                       (self.id,))
        row = cursor.fetchone()
        return row[0] if row else None

    def updateBranchFromRemote(self, db, remote, branch_name):
        if branch_name == self.getMainBranch(db).name:
            raise Exception, "refusing to update main branch ('%s')" % branch_name

        remote_id = "t%d" % int((time.time() * 1e6) % 1e9)

        self.runRelay("remote", "add", remote_id, remote)
        try:
            self.runRelay("fetch", remote_id, "refs/heads/%s:refs/remotes/%s/%s" % (branch_name, remote_id, branch_name))
            self.runRelay("push", "-f", "origin", "refs/remotes/%s/%s:refs/heads/%s" % (remote_id, branch_name, branch_name))
        finally:
            self.runRelay("remote", "rm", remote_id)

    def fetchTemporaryFromRemote(self, remote, ref):
        remote_id = "t%d" % int((time.time() * 1e6) % 1e9)

        self.runRelay("remote", "add", remote_id, remote)
        try:
            self.runRelay("fetch", remote_id, "%s:refs/remotes/%s/temporary" % (ref, remote_id))
            self.runRelay("push", "-f", "origin", "refs/remotes/%s/temporary:refs/temporary/%s" % (remote_id, remote_id))
            return self.revparse("refs/temporary/%s" % remote_id)
        finally:
            self.runRelay("remote", "rm", remote_id)

    @staticmethod
    def readObject(repository_path, object_type, object_sha1):
        git = process([configuration.executables.GIT, 'cat-file', object_type, object_sha1], stdout=PIPE, stderr=PIPE, cwd=repository_path)
        stdout, stderr = git.communicate()
        if git.returncode == 0: return stdout
        else: raise Exception, "'git cat-file' failed: %s" % stderr.strip()

    @staticmethod
    def lstree(remote, regexp=None):
        if regexp: name_check = lambda item: bool(regexp.match(item[1]))
        else: name_check = lambda item: True

        git = process([configuration.executables.GIT, 'ls-remote', remote], stdout=PIPE, stderr=PIPE, cwd="/tmp")
        stdout, stderr = git.communicate()

        if git.returncode == 0: return filter(name_check, (line.split() for line in stdout.splitlines()))
        else: raise Exception, "'git ls-remote' failed: %s" % stderr.strip()

    def findInterestingTag(self, db, sha1):
        cursor = db.cursor()
        cursor.execute("SELECT name FROM tags WHERE repository=%s AND sha1=%s",
                       (self.id, sha1))

        tags = [tag for (tag,) in cursor]

        try:
            from customization.filtertags import filterTags
            tags = filterTags(self, tags)
        except ImportError:
            pass

        if tags: return tags[0]
        else: return None

class CommitUserTime:
    def __init__(self, name, email, time):
        self.name = name
        self.email = email
        self.time = time

    def __getIds(self, db):
        cache = db.storage["CommitUserTime"]
        cached = cache.get((self.name, self.email))
        if cached: return cached

        cursor = db.cursor()
        cursor.execute("""SELECT usergitemails.uid, gitusers.id
                            FROM gitusers
                 LEFT OUTER JOIN usergitemails USING (email)
                           WHERE gitusers.fullname=%s
                             AND gitusers.email=%s""",
                       (self.name, self.email))
        row = cursor.fetchone()
        if row:
            user_id, gituser_id = row
        else:
            cursor.execute("INSERT INTO gitusers (fullname, email) VALUES (%s, %s) RETURNING id", (self.name, self.email))
            gituser_id = cursor.fetchone()[0]
            cursor.execute("SELECT uid FROM usergitemails WHERE email=%s", (self.email,))
            row = cursor.fetchone()
            user_id = row[0] if row else None
        cache[(self.name, self.email)] = user_id, gituser_id

        return user_id, gituser_id

    def getUserId(self, db):
        return self.__getIds(db)[0]

    def getGitUserId(self, db):
        return self.__getIds(db)[1]

    def getFullname(self, db):
        user_id = self.getUserId(db)
        if user_id is None: return self.name
        else:
            import dbutils
            return dbutils.User.fromId(db, user_id).fullname

    @staticmethod
    def fromValue(value):
        match = re_author_committer.match(value)
        return CommitUserTime(convertUTF8(match.group(1)), convertUTF8(match.group(2)), time.gmtime(int(match.group(3).split(" ")[0])))

class Commit:
    def __init__(self, repository, id, sha1, parents, author, committer, message, tree):
        self.repository = repository
        self.id = id
        self.sha1 = sha1
        self.parents = parents
        self.author = author
        self.committer = committer
        self.message = message
        self.tree = tree

    def __cache(self, db):
        cache = db.storage["Commit"]
        if self.id: cache[self.id] = self
        cache[self.sha1] = self

    @staticmethod
    def fromGitObject(db, repository, gitobject, commit_id=None):
        assert gitobject.type == "commit"

        data = gitobject.data
        parents = []

        while True:
            line, data = data.split('\n', 1)

            if not line:
                break

            key, value = line.split(' ', 1)

            if key == 'tree': tree = value
            elif key == 'parent': parents.append(value)
            elif key == 'author': author = CommitUserTime.fromValue(value)
            elif key == 'committer': committer = CommitUserTime.fromValue(value)

        commit = Commit(repository, commit_id, gitobject.sha1, parents, author, committer, convertUTF8(data), tree)
        commit.__cache(db)
        return commit

    @staticmethod
    def fromSHA1(db, repository, sha1, commit_id=None):
        return Commit.fromGitObject(db, repository, repository.fetch(sha1), commit_id)

    @staticmethod
    def fromId(db, repository, commit_id):
        commit = db.storage["Commit"].get(commit_id)
        if not commit:
            cursor = db.cursor()
            cursor.execute("SELECT sha1 FROM commits WHERE id=%s", (commit_id,))
            sha1 = cursor.fetchone()[0]
            commit = Commit.fromSHA1(db, repository, sha1, commit_id)
        return commit

    def __hash__(self): return hash(self.sha1)
    def __eq__(self, other): return self.sha1 == str(other)
    def __ne__(self, other): return self.sha1 != str(other)
    def __str__(self): return self.sha1
    def __repr__(self):
        if self.id is None: return "Commit(sha1=%r)" % self.sha1
        else: return "Commit(sha1=%r, id=%d)" % (self.sha1, self.id)

    def summary(self, maxlen=None):
        summary = self.message.split("\n", 1)[0].strip()
        if maxlen and len(summary) > maxlen:
            summary = summary[:maxlen - 3].strip() + "..."
        return summary

    def niceSummary(self):
        try:
            summary, rest = self.message.split("\n", 1)

            if summary.startswith("fixup! ") or summary.startswith("squash! "):
                fixup_summary = rest.strip().split("\n", 1)[0]
                if fixup_summary.strip():
                    what = summary[:summary.index("!")]
                    return "[%s] %s" % (what, fixup_summary)

            return summary
        except:
            return self.summary()

    def getId(self, db):
        if self.id is None:
            cursor = db.cursor()
            cursor.execute("SELECT id FROM commits WHERE sha1=%s", (self.sha1,))
            self.id = cursor.fetchone()[0]
            self.__cache(db)
        return self.id

    def findInterestingTag(self, db):
        return self.repository.findInterestingTag(db, self.sha1)

    def describe(self, db):
        if db:
            tag = self.findInterestingTag(db)
            if tag: return tag
        return self.sha1[:8]

    def isAncestorOf(self, other):
        if isinstance(other, Commit):
            if self.repository != other.repository: return False
            other_sha1 = other.sha1
        else:
            other_sha1 = str(other)

        return self.repository.mergebase([self.sha1, other_sha1]) == self.sha1

    def getFileSHA1(self, path):
        try:
            tree = Tree.fromPath(self, os.path.dirname(path))
            return tree[os.path.basename(path)].sha1
        except KeyError:
            return None

RE_LSTREE_LINE = re.compile("^([0-9]{6}) (blob|tree|commit) ([0-9a-f]{40})  *([0-9]+|-)\t(.*)$")

class Tree:
    class Entry:
        class Mode(int):
            def __new__(cls, value):
                return super(Tree.Entry.Mode, cls).__new__(cls, int(value, 8))

            def __str__(self):
                if stat.S_ISDIR(self):
                    return "d---------"
                elif self == 0160000:
                    return "m---------"
                else:
                    if stat.S_ISLNK(self): string = "l"
                    else: string = "-"

                    flags = ["---", "--x", "-w-", "-wx", "r--", "r-x", "rw-", "rwx"]
                    return string + flags[(self & 0700) >> 6] + flags[(self & 070) >> 3] + flags[self & 07]

        def __init__(self, name, mode, type, sha1, size):
            self.name = name
            self.mode = Tree.Entry.Mode(mode)
            self.type = type
            self.sha1 = sha1
            self.size = size

        def __str__(self):
            return self.name

        def __repr__(self):
            return "[%s %s %s %s%s]" % (self.mode, self.type, self.name, self.sha1[:8], " %d" % self.size if self.size else "")

    def __init__(self, entries, commit=None):
        self.__entries_list = entries
        self.__entries_dict = dict([(entry.name, entry) for entry in entries])

    def __getitem__(self, item):
        if type(item) == int:
            return self.__entries_list[item]
        else:
            return self.__entries_dict[str(item)]

    def __len__(self):
        return len(self.__entries_list)
    def __iter__(self):
        return iter(self.__entries_list)

    def keys(self):
        return self.__entries_dict.keys()
    def items(self):
        return self.__entries_dict.items()
    def values(self):
        return self.__entries_dict.values()
    def get(self, key, default=None):
        return self.__entries_dict.get(key, default)

    @staticmethod
    def fromPath(commit, path):
        assert path[0] == "/"

        if path == "/":
            what = commit.sha1
        else:
            if path[-1] != "/": path += "/"
            what = "%s:%s" % (commit.sha1, path[1:])

        entries = []

        for line in commit.repository.run("ls-tree", "-l", what).splitlines():
            match = RE_LSTREE_LINE.match(line)
            assert match

            entries.append(Tree.Entry(match.group(5), match.group(1), match.group(2), match.group(3), int(match.group(4)) if match.group(2) == "blob" else None))

        return Tree(entries)

    @staticmethod
    def fromSHA1(repository, sha1):
        data = repository.fetch(sha1).data
        entries = []

        while len(data):
            space = data.index(" ")
            null = data.index("\0", space + 1)

            mode = data[:space]
            name = data[space + 1:null]

            sha1_binary = data[null + 1:null + 21]
            sha1 = "".join([("%02x" % ord(c)) for c in sha1_binary])

            entry_object = repository.fetch(sha1, fetchData=False)

            entries.append(Tree.Entry(name, mode, entry_object.type, sha1, entry_object.size))

            data = data[null + 21:]

        return Tree(entries)

def getTaggedCommit(repository, sha1):
    """Returns the SHA-1 of the tagged commit.

       If the supplied SHA-1 sum is a commit object, then it is returned,
       otherwise it must be a tag object, which is parsed to retrieve the
       tagged object SHA-1 sum."""

    while True:
        git_object = repository.fetch(sha1)

        if git_object.type == "commit":
            return sha1
        elif git_object.type != "tag":
            return

        sha1 = git_object.data.split("\n", 1)[0].split(" ", 1)[-1]

class Blame:
    def __init__(self, from_commit, to_commit):
        assert from_commit.repository == to_commit.repository

        self.repository = from_commit.repository
        self.from_commit = from_commit
        self.to_commit = to_commit
        self.commits = []
        self.__commit_ids = {}

    def blame(self, db, path, first_line, last_line):
        output = self.repository.run("blame",
                                     "--porcelain",
                                     "-L", "%d,%d" % (first_line, last_line),
                                     "%s..%s" % (self.from_commit.sha1, self.to_commit.sha1),
                                     "--", path)

        inlines = iter(output.splitlines())
        lines = []

        try:
            while True:
                sha1, original_line, current_line = inlines.next().split(" ")[:3]

                original_line = int(original_line)
                current_line = int(current_line)

                author = None
                author_email = None

                line = inlines.next()
                while not line.startswith("\t"):
                    if line.startswith("author "): author = line[7:]
                    elif line.startswith("author-mail "): author_email = line[13:-1]
                    elif line.startswith("summary "): pass
                    line = inlines.next()

                if sha1 not in self.__commit_ids:
                    commit = Commit.fromSHA1(db, self.repository, sha1)

                    self.__commit_ids[sha1] = len(self.commits)
                    self.commits.append({ "sha1": sha1,
                                          "author_name": author,
                                          "author_email": author_email,
                                          "summary": commit.niceSummary(),
                                          "message": commit.message,
                                          "original": sha1 == self.from_commit.sha1,
                                          "current": sha1 == self.to_commit.sha1 })

                lines.append({ "offset": current_line,
                               "commit": self.__commit_ids[sha1] })
        except StopIteration:
            pass

        return lines

class FetchCommits(threading.Thread):
    def __init__(self, repository, sha1s):
        super(FetchCommits, self).__init__()

        self.repository = repository
        self.sha1s = sha1s
        self.gitobjects = []
        self.commits = None
        self.error = None
        self.joined = False

        self.start()

    def run(self):
        try:
            batch = process([configuration.executables.GIT, 'cat-file', '--batch'], stdin=PIPE, stdout=PIPE, stderr=STDOUT, cwd=self.repository.path)

            stdout, stderr = batch.communicate("\n".join(self.sha1s.keys()) + "\n")

            gitobjects = []

            for sha1, commit_id in self.sha1s.items():
                line, stdout = stdout.split("\n", 1)

                try: object_sha1, object_type, object_size = line.split(" ")
                except: raise Exception, "unexpected header line: %r" % line

                assert object_sha1 == sha1, "%s != %s" % (object_sha1, sha1)
                assert object_type == "commit"

                object_size = int(object_size)

                object_data = stdout[:object_size]
                stdout = stdout[object_size + 1:]

                gitobjects.append((GitObject(object_sha1, object_type, object_size, object_data), commit_id))

            self.gitobjects = gitobjects
        except:
            self.error = format_exc()

    def getCommits(self, db):
        self.join()

        for gitobject, commit_id in self.gitobjects:
            Commit.fromGitObject(db, self.repository, gitobject, commit_id)
