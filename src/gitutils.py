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

import subprocess
import re
import time
import atexit
import os
import traceback
import threading
import tempfile
import shutil
import stat
import contextlib
import base64

import base
import configuration
import textutils
import htmlutils
import communicate
import diff.parse

re_author_committer = re.compile("(.*) <(.*)> ([0-9]+ [-+][0-9]+)")
re_sha1 = re.compile("^[A-Za-z0-9]{40}$")

REPOSITORY_RELAYCOPY_DIR = os.path.join(configuration.paths.DATA_DIR, "relay")
REPOSITORY_WORKCOPY_DIR = os.path.join(configuration.paths.DATA_DIR, "temporary")

# Reference used to keep various commits alive.
KEEPALIVE_REF_CHAIN = "refs/internal/keepalive-chain"
KEEPALIVE_REF_PREFIX = "refs/keepalive/"

# This is what an empty tree object hashes to.
EMPTY_TREE_SHA1 = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

def same_filesystem(pathA, pathB):
    return os.stat(pathA).st_dev == os.stat(pathB).st_dev

def getGitEnvironment(author=True, committer=True):
    env = {}
    def name(parameter):
        if parameter is True:
            return "Critic System"
        elif isinstance(parameter, CommitUserTime):
            return parameter.name
        else:
            return parameter.fullname
    def email(parameter):
        if parameter is True or not parameter.email:
            return configuration.base.SYSTEM_USER_EMAIL
        else:
            return parameter.email
    if author:
        env["GIT_AUTHOR_NAME"] = name(author)
        env["GIT_AUTHOR_EMAIL"] = email(author)
    if committer:
        env["GIT_COMMITTER_NAME"] = name(committer)
        env["GIT_COMMITTER_EMAIL"] = email(committer)
    return env

class GitError(base.Error):
    pass

class GitReferenceError(GitError):
    """Exception raised on an invalid SHA-1s or refs."""

    def __init__(self, message, sha1=None, ref=None, repository=None):
        super(GitReferenceError, self).__init__(message)
        self.sha1 = sha1
        self.ref = ref
        self.repository = repository

class GitCommandError(GitError):
    """Exception raised when a Git command fails."""

    def __init__(self, cmdline, output, cwd):
        super(GitCommandError, self).__init__("'%s' failed: %s (in %s)" % (cmdline, output, cwd))
        self.cmdline = cmdline
        self.output = output
        self.cwd = cwd

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
        raise IndexError("GitObject index out of range: %d" % index)

class GitHttpBackendError(GitError):
    def __init__(self, returncode, stderr):
        message = "Git failed!"
        if returncode < 0:
            message = "Git terminated by signal %d!" % -returncode
        elif returncode > 0:
            message = "Git exited with status %d!" % returncode
        if stderr.strip():
            message += "\n" + stderr
        super(GitHttpBackendError, self).__init__(message)
        self.returncode = returncode
        self.stderr = stderr

class GitHttpBackendNeedsUser(GitError):
    pass

class NoSuchRepository(base.Error):
    """Exception raised by Repository.fromName() for invalid names."""

    def __init__(self, value):
        super(NoSuchRepository, self).__init__("No such repository: %s" % str(value))
        self.value = value

class Repository:
    class FromParameter:
        def __init__(self, db): self.db = db
        def __call__(self, value): return Repository.fromParameter(self.db, value)

    def __init__(self, db=None, repository_id=None, parent=None, name=None, path=None):
        assert path

        self.id = repository_id
        self.name = name
        self.path = path
        self.parent = parent
        self.environ = {}

        self.__batch = None
        self.__batchCheck = None
        self.__cacheBlobs = False
        self.__cacheDisabled = False

        if db:
            self.__db = db
            db.atexit(self.__terminate)
        else:
            self.__db = None
            atexit.register(self.__terminate)

    def __str__(self):
        return self.path

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stopBatch()
        return False

    @property
    def __environ(self):
        env = {}
        env.update(os.environ)
        env.update(configuration.executables.GIT_ENV)
        env.update(self.environ)
        return env

    def getURL(self, db, user):
        return Repository.constructURL(db, user, self.path)

    @staticmethod
    def constructURL(db, user, path):
        path = os.path.relpath(path, configuration.paths.GIT_DIR)
        url_type = user.getPreference(db, "repository.urlType")

        if url_type == "git":
            url_format = "git://%s/%s"
        elif url_type in ("ssh", "host"):
            if url_type == "ssh":
                prefix = "ssh://%s"
            else:
                prefix = "%s:"
            url_format = prefix + os.path.join(configuration.paths.GIT_DIR, "%s")
        else:
            import dbutils
            url_prefix = dbutils.getURLPrefix(db, user)
            return "%s/%s" % (url_prefix, path)

        return url_format % (configuration.base.HOSTNAME, path)

    def enableBlobCache(self):
        assert self.__db
        self.__cacheBlobs = True

    def disableCache(self):
        self.__cacheDisabled = True

    def checkAccess(self, db, access_type):
        import auth
        assert access_type in ("read", "modify")
        auth.AccessControl.accessRepository(db, access_type, self)

    @staticmethod
    def fromId(db, repository_id, for_modify=False):
        if repository_id in db.storage["Repository"]:
            repository = db.storage["Repository"][repository_id]
        else:
            cursor = db.readonly_cursor()
            cursor.execute("SELECT parent, name, path FROM repositories WHERE id=%s", (repository_id,))

            parent_id, name, path = cursor.fetchone()
            parent = None if parent_id is None else Repository.fromId(db, parent_id)
            repository = Repository(db, repository_id=repository_id, parent=parent, name=name, path=path)

        # Raises auth.AccessDenied if access should not be allowed.
        repository.checkAccess(db, "modify" if for_modify else "read")

        db.storage["Repository"][repository_id] = repository
        db.storage["Repository"][repository.name] = repository

        return repository

    @staticmethod
    def fromName(db, name, for_modify=False):
        if name in db.storage["Repository"]:
            return db.storage["Repository"][name]
        else:
            cursor = db.readonly_cursor()
            cursor.execute("SELECT id FROM repositories WHERE name=%s", (name,))
            row = cursor.fetchone()
            if not row:
                return None
            repository_id, = row
            return Repository.fromId(db, repository_id, for_modify)

    @staticmethod
    def fromParameter(db, parameter):
        try: repository = Repository.fromId(db, int(parameter))
        except: repository = Repository.fromName(db, parameter)
        if repository: return repository
        else: raise NoSuchRepository(parameter)

    @staticmethod
    def fromSHA1(db, sha1):
        cursor = db.readonly_cursor()
        cursor.execute("SELECT id FROM repositories ORDER BY id ASC")
        for (repository_id,) in cursor:
            repository = Repository.fromId(db, repository_id)
            if repository.iscommit(sha1): return repository
        raise GitReferenceError(
            "Couldn't find commit %s in any repository." % sha1,
            sha1=sha1)

    @staticmethod
    def fromPath(db, path, for_modify=False):
        cursor = db.readonly_cursor()
        cursor.execute("SELECT id FROM repositories WHERE path=%s", (path,))
        for (repository_id,) in cursor:
            return Repository.fromId(db, repository_id, for_modify=for_modify)
        raise NoSuchRepository(path)

    @staticmethod
    def fromAPI(api_repository):
        return api_repository._impl.getInternal(api_repository.critic)

    def __terminate(self, db=None):
        self.stopBatch()

    def __startBatch(self):
        if self.__batch is None:
            self.__batch = subprocess.Popen(
                [configuration.executables.GIT, 'cat-file', '--batch'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, cwd=self.path, env=self.__environ)

    def __startBatchCheck(self):
        if self.__batchCheck is None:
            self.__batchCheck = subprocess.Popen(
                [configuration.executables.GIT, 'cat-file', '--batch-check'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, cwd=self.path, env=self.__environ)

    def stopBatch(self):
        if self.__batch:
            try: os.kill(self.__batch.pid, 9)
            except: pass
            try: self.__batch.wait()
            except: pass
            self.__batch = None
        if self.__batchCheck:
            try: os.kill(self.__batchCheck.pid, 9)
            except: pass
            try: self.__batchCheck.wait()
            except: pass
            self.__batchCheck = None

    @staticmethod
    def forEach(db, fn):
        for key, repository in db.storage["Repository"].items():
            if isinstance(key, int):
                fn(db, repository)

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

            key, value = list(map(str.strip, line.split("=")))

            if key == "url":
                path = os.path.abspath(os.path.join(self.path, value))

                cursor = db.readonly_cursor()
                cursor.execute("SELECT id FROM repositories WHERE path=%s", (path,))

                row = cursor.fetchone()
                if row:
                    return Repository.fromId(db, row[0])
                else:
                    return None
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

        try: stdin.write(sha1 + '\n')
        except: raise GitError("failed when writing to 'git cat-file' stdin: %s" % stdout.read())

        line = stdout.readline()

        if line == ("%s missing\n" % sha1):
            raise GitReferenceError("%s missing from %s" % (sha1[:8], self.path), sha1=sha1, repository=self)

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

    def runCustom(self, cwd, command, *arguments, **kwargs):
        argv = [configuration.executables.GIT, command]
        argv.extend(arguments)
        stdin_data = kwargs.get("input")
        if stdin_data is None: stdin = None
        else: stdin = subprocess.PIPE
        env = self.__environ
        env.update(kwargs.get("env", {}))
        if "GIT_DIR" in env: del env["GIT_DIR"]
        git = subprocess.Popen(argv, stdin=stdin, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=cwd, env=env)
        stdout, stderr = git.communicate(stdin_data)
        if kwargs.get("check_errors", True):
            if git.returncode == 0:
                if kwargs.get("include_stderr", False):
                    return stdout + stderr
                else:
                    return stdout
            else:
                cmdline = " ".join(argv)
                output = stderr.strip()
                raise GitCommandError(cmdline, output, cwd)
        else:
            return git.returncode, stdout, stderr

    def createBranch(self, name, startpoint):
        self.run("branch", name, startpoint)

    def deleteBranch(self, name):
        self.run("branch", "-D", name)

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
        except: sha1s = list(map(str, commit_or_commits))

        assert len(sha1s) >= 2

        return self.run("merge-base", *sha1s).strip()

    def getCommonAncestor(self, commit_or_commits):
        try: sha1s = commit_or_commits.parents
        except: sha1s = list(commit_or_commits)

        assert len(sha1s) >= 2

        mergebases = [self.mergebase([sha1s[0], sha1]) for sha1 in sha1s[1:]]

        if len(mergebases) == 1: return mergebases[0]
        else: return self.getCommonAncestor(mergebases)

    def revparse(self, name):
        try:
            return self.run("rev-parse", "--verify", "--quiet", name).strip()
        except GitCommandError as error:
            raise GitReferenceError(
                "'git rev-parse' failed: %s" % error.output.strip(),
                ref=name, repository=self)

    def revlist(self, included, excluded, *args, **kwargs):
        args = list(args)
        args.extend([str(ref) for ref in included])
        args.extend(['^' + str(ref) for ref in excluded])
        if "paths" in kwargs:
            args.append("--")
            args.extend(kwargs["paths"])
        return self.run('rev-list', *args).splitlines()

    def iscommit(self, name):
        try:
            output = self.run("cat-file", "-t", name)
        except GitCommandError:
            return False
        else:
            return output.strip() == "commit"

    def isref(self, name):
        try:
            self.revparse(name)
            return True
        except GitReferenceError:
            return False

    def createref(self, name, value):
        assert name.startswith("refs/")
        self.run("update-ref", name, str(value), "0" * 40)

    def updateref(self, name, new_value, old_value=None):
        assert name.startswith("refs/")
        args = ["update-ref", name, str(new_value)]
        if old_value is not None:
            args.append(str(old_value))
        self.run(*args)

    def deleteref(self, name, value=None):
        assert name.startswith("refs/")
        args = ["update-ref", "-d", name]
        if value is not None:
            args.append(str(value))
        self.run(*args)

    def keepalive(self, commit):
        sha1 = str(commit)
        self.run("update-ref", KEEPALIVE_REF_PREFIX + sha1, sha1)
        return sha1

    def packKeepaliveRefs(self):
        """
        Pack the repository's keepalive refs into a single chain
        """

        def splitRefs(output):
            return [(int(timestamp.split()[0]), sha1, timestamp)
                    for sha1, _, timestamp in
                    (line.partition(":")
                     for line in
                     output.splitlines())
                    # Skip the root commit, which has summary "Root".
                    if len(sha1) == 40]

        loose_keepalive_refs = splitRefs(
            self.run("for-each-ref",
                     "--sort=committerdate",
                     "--format=%(objectname):%(committerdate:raw)",
                     KEEPALIVE_REF_PREFIX))

        if not loose_keepalive_refs:
            # No loose refs => no need to (re)pack.
            return

        try:
            old_value = self.revparse(KEEPALIVE_REF_CHAIN)
        except GitReferenceError:
            old_value = "0" * 40
            packed_keepalive_refs = []
        else:
            packed_keepalive_refs = splitRefs(
                self.run("log",
                         "--first-parent",
                         "--date=raw",
                         "--format=%s:%cd",
                         old_value))

        keepalive_refs = sorted(packed_keepalive_refs + loose_keepalive_refs)

        env = getGitEnvironment()

        def withDates(env, timestamp):
            env["GIT_AUTHOR_DATE"] = timestamp
            env["GIT_COMMITTER_DATE"] = timestamp
            return env

        # Note: we don't keep the generated commits alive by updating refs while
        # doing this.  Since commit-tree itself produces unreferenced objects,
        # it seems unlikely it will ever run an automatic GC, and if someone
        # else triggers a GC while we're working, and it prunes our objects,
        # then we'll fail, which is no big deal (we'd just leave the existing
        # keepalive refs unmodified.)
        #
        # Also note: in most cases, the repacked keepalive chain will end up
        # reusing the commit objects from the existing keepalive chain, since
        # all meta-data in the generated commits come from the commits that we
        # keep alive, and the order stable.

        try:
            processed = set()

            new_value = self.run(
                "commit-tree", EMPTY_TREE_SHA1, input="Root",
                env=withDates(env, keepalive_refs[0][2])).strip()

            for _, sha1, timestamp in keepalive_refs:
                if sha1 in processed:
                    continue
                processed.add(sha1)

                new_value = self.run(
                    "commit-tree", EMPTY_TREE_SHA1, "-p", new_value, "-p", sha1,
                    input=sha1, env=withDates(env, timestamp)).strip()

            self.updateref(KEEPALIVE_REF_CHAIN, new_value, old_value)
        except GitCommandError:
            # No big deal if this fails here; this is just a maintenance
            # operation.  We'll try again another day.
            return False

        for _, sha1, _ in loose_keepalive_refs:
            try:
                self.deleteref(KEEPALIVE_REF_PREFIX + sha1, sha1)
            except GitCommandError:
                # Ignore failures to delete loose keepalive refs.
                pass

        return True

    @contextlib.contextmanager
    def temporaryref(self, commit=None):
        if commit:
            sha1 = self.revparse(str(commit))
            name = "refs/temporary/%s" % sha1
            self.createref(name, sha1)
        else:
            sha1 = None
            name = "refs/temporary/%s-%s" % (time.strftime("%Y%m%d%H%M%S"),
                                             base64.b32encode(os.urandom(10)))
        try:
            yield name
        finally:
            self.deleteref(name, sha1)

    def __copy(self, identifier, flavor):
        base_args = ["clone", "--quiet"]

        if flavor == "relay":
            base_args.append("--bare")
            base_dir = REPOSITORY_RELAYCOPY_DIR
        else:
            assert flavor == "work"
            base_dir = REPOSITORY_WORKCOPY_DIR

        class Copy(object):
            def __init__(self, origin, path, name):
                self.origin = origin
                self.path = path
                self.name = name
            def run(self, *args, **kwargs):
                return self.origin.runCustom(
                    os.path.join(self.path, self.name), *args, **kwargs)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                shutil.rmtree(self.path)
                return False

        path = tempfile.mkdtemp(prefix="%s_%s_" % (self.name, identifier),
                                dir=base_dir)
        name = os.path.basename(self.path)

        local_args = base_args[:]
        if not same_filesystem(self.path, path):
            local_args.append("--shared")
        local_args.extend([self.path, name])

        fallback_args = base_args[:]
        fallback_args.extend(["file://" + os.path.abspath(self.path), name])

        try:
            # Try cloning with --local (implied by using a plain path as the
            # repository URL.)  This may fail due to inaccessible pack-*.keep
            # files in the repository.
            self.runCustom(path, *local_args)
        except GitCommandError:
            try:
                # Try cloning without --local (implied by using a file://
                # repository URL.)  This is slower and uses more disk space, but
                # is immune to the problems with inaccessible pack-*.keep files.
                self.runCustom(path, *fallback_args)
            except GitCommandError:
                shutil.rmtree(path)
                raise

        return Copy(self, path, name)

    def relaycopy(self, identifier):
        return self.__copy(identifier, "relay")

    def workcopy(self, identifier):
        return self.__copy(identifier, "work")

    def replaymerge(self, db, user, commit):
        with self.workcopy(commit.sha1) as workcopy:
            with self.temporaryref(commit) as ref_name:
                # Fetch the merge to replay from the main repository into the work copy.
                workcopy.run('fetch', 'origin', ref_name)

            parent_sha1s = commit.parents

            # Create and check out a branch at first parent.
            workcopy.run('checkout', '-b', 'replay', parent_sha1s[0])

            # Then perform the merge with the other parents.
            returncode, stdout, stderr = workcopy.run("merge", *parent_sha1s[1:],
                env=getGitEnvironment(author=commit.author),
                check_errors=False)

            # If the merge produced conflicts, just stage and commit them:
            if returncode != 0:
                # Reset any submodule gitlinks with conflicts: since we don't
                # have the submodules checked out, "git commit --all" below
                # may fail to index them.
                for line in stdout.splitlines():
                    if line.startswith("CONFLICT (submodule):"):
                        submodule_path = line.split()[-1]
                        workcopy.run("reset", "--", submodule_path, check_errors=False)

                # Then stage and commit the result, with conflict markers and all.
                workcopy.run("commit", "--all", "--message=replay of merge that produced %s" % commit.sha1,
                             env=getGitEnvironment(author=commit.author))

            sha1 = workcopy.run("rev-parse", "HEAD").strip()

            # Then push the commit to the main repository.
            workcopy.run('push', 'origin', 'HEAD:refs/keepalive/' + sha1)

            commit = Commit.fromSHA1(db, self, sha1)

            # Finally, return the resulting commit.
            return commit

    def getSignificantBranches(self, db):
        """Return an iterator of "significant" branches

           A branch is considered significant if it is referenced by the
           repository's HEAD (if that's a symbolic ref) or if it is set up to
           track a remote branch."""
        import dbutils
        head_branch = self.getHeadBranch(db)
        if head_branch:
            yield head_branch
        cursor = db.readonly_cursor()
        cursor.execute(
            """SELECT local_name
                 FROM trackedbranches
                 JOIN branches ON (branches.repository=trackedbranches.repository
                               AND branches.name=trackedbranches.local_name)
                WHERE branches.repository=%s
                  AND branches.type='normal'
             ORDER BY trackedbranches.id ASC""",
                       (self.id,))
        for (branch_name,) in cursor:
            if head_branch and head_branch.name == branch_name:
                continue
            yield dbutils.Branch.fromName(db, self, branch_name)

    def getDefaultRemote(self, db):
        cursor = db.readonly_cursor()
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
        cursor = db.readonly_cursor()
        cursor.execute("""SELECT 1
                            FROM trackedbranches
                           WHERE repository=%s
                             AND local_name=%s
                             AND NOT disabled""",
                       (self.id, branch_name))
        if cursor.fetchone():
            # Don't update a branch that the branch tracker service owns;
            # instead just assume it's already up-to-date.
            return

        if not branch_name.startswith("refs/"):
            branch_name = "refs/heads/%s" % branch_name

        with self.relaycopy("updateBranchFromRemote") as relay:
            try:
                relay.run("fetch", remote, branch_name)
            except GitCommandError as error:
                if error.output.startswith("fatal: Couldn't find remote ref "):
                    raise GitReferenceError("Couldn't find ref %s in %s." % (branch_name, remote),
                                            ref=branch_name, repository=remote)
                raise

            relay.run("push", "-f", "origin", "FETCH_HEAD:%s" % branch_name)

    @contextlib.contextmanager
    def fetchTemporaryFromRemote(self, db, remote, ref):
        with self.temporaryref() as temporary_ref:
            try:
                self.run("fetch", remote, "%s:%s" % (ref, temporary_ref))
            except GitCommandError as error:
                if error.output.startswith("fatal: Couldn't find remote ref "):
                    raise GitReferenceError("Couldn't find ref %s in %s." % (ref, remote), ref=ref, repository=remote)
                elif error.output.startswith("fatal: Invalid refspec "):
                    raise GitReferenceError("Invalid ref %r." % ref, ref=ref)
                raise

            sha1 = self.run("rev-parse", "--verify", temporary_ref + "^{commit}").strip()

            self.processCommits(db, sha1)

            yield sha1

    @staticmethod
    def readObject(repository_path, object_type, object_sha1):
        argv = [configuration.executables.GIT, 'cat-file', object_type, object_sha1]
        git = subprocess.Popen(argv, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=repository_path)
        stdout, stderr = git.communicate()
        if git.returncode != 0:
            raise GitCommandError(" ".join(argv), stderr.strip(), repository_path)
        return stdout

    @staticmethod
    def lsremote(remote, include_heads=False, include_tags=False, pattern=None, regexp=None):
        if regexp: name_check = lambda item: bool(regexp.match(item[1]))
        else: name_check = lambda item: True

        argv = [configuration.executables.GIT, 'ls-remote']

        if include_heads: argv.append("--heads")
        if include_tags: argv.append("--tags")

        argv.append(remote)

        if pattern: argv.append(pattern)

        git = subprocess.Popen(argv, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = git.communicate()

        if git.returncode == 0:
            return filter(name_check, (line.split() for line in stdout.splitlines()))
        else:
            cmdline = " ".join(argv)
            output = stderr.strip()
            cwd = os.getcwd()
            raise GitCommandError(cmdline, output, cwd)

    def findInterestingTag(self, db, sha1):
        cursor = db.readonly_cursor()
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

    def getHead(self, db):
        return Commit.fromSHA1(db, self, self.revparse("HEAD"))

    def getHeadBranch(self, db):
        """Return the branch that HEAD references

           None is returned if HEAD is not a symbolic ref or if it references a
           ref not under refs/heads/."""
        import dbutils
        try:
            ref_name = self.run("symbolic-ref", "--quiet", "HEAD").strip()
        except GitCommandError:
            # HEAD is not a symbolic ref.
            pass
        else:
            if ref_name.startswith("refs/heads/"):
                branch_name = ref_name[len("refs/heads/"):]
                return dbutils.Branch.fromName(db, self, branch_name)

    def isEmpty(self):
        try:
            self.revparse("HEAD")
            return False
        except GitError:
            return True

    def invokeGitHttpBackend(self, req, user, path):
        request_environ = req.getEnvironment()

        environ = { "GIT_HTTP_EXPORT_ALL": "true",
                    "REMOTE_ADDR": request_environ.get("REMOTE_ADDR", "unknown"),
                    "PATH_TRANSLATED": os.path.join(self.path, path),
                    "REQUEST_METHOD": req.method,
                    "QUERY_STRING": req.query }

        if "CONTENT_TYPE" in request_environ:
            environ["CONTENT_TYPE"] = request_environ["CONTENT_TYPE"]

        for name, value in req.getEnvironment().items():
            if name.startswith("HTTP_"):
                environ[name] = value

        if not user.isAnonymous():
            environ["REMOTE_USER"] = user.name
        elif not configuration.base.ALLOW_ANONYMOUS_USER \
                or path == "git-receive-pack" \
                or req.getParameter("service", None) == "git-receive-pack":
            # The git-receive-pack service fails without a user, so request
            # authorization.
            raise GitHttpBackendNeedsUser

        git_http_backend = communicate.Communicate(subprocess.Popen(
            [configuration.executables.GIT, "http-backend"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=environ))

        def produceInput():
            if req.method not in ("POST", "PUT"):
                return None
            else:
                data = req.read(65536)
                if not data:
                    return None
                return data

        def handleHeaderLine(line):
            line = line.strip()

            if not line:
                req.start()
                git_http_backend.setCallbacks(stdout=handleOutput)
                return

            name, _, value = line.partition(":")
            name = name.strip()
            value = value.strip()

            if name.lower() == "status":
                status_code, _, status_text = value.partition(" ")
                req.setStatus(int(status_code), status_text.strip())
            elif name.lower() == "content-type":
                req.setContentType(value)
            else:
                req.addResponseHeader(name, value)

        def handleOutput(data):
            req.write(data)

        git_http_backend.setInput(produceInput)
        git_http_backend.setCallbacks(stdout_line=handleHeaderLine)

        try:
            _, stderr = git_http_backend.run()
        except communicate.ProcessError as error:
            raise GitHttpBackendError(error.process.returncode, error.stderr)

    def describe(self, db, sha1):
        tag = self.findInterestingTag(db, sha1)
        if tag:
            return tag

        commit = Commit.fromSHA1(db, self, sha1)

        for branch in self.getSignificantBranches(db):
            if commit == branch.head_sha1:
                return "tip of " + branch.name
            elif commit.isAncestorOf(branch.head_sha1):
                return branch.name

        return None

    def processCommits(self, db, sha1):
        sha1 = self.run("rev-parse", "--verify", "--quiet",
                        sha1 + "^{commit}").strip()

        cursor = db.readonly_cursor()
        cursor.execute("SELECT 1 FROM commits LIMIT 1")
        emptydb = cursor.fetchone() is None

        stack = []
        commits = set()
        commit_users = set()

        commits_values = []
        edges_values = []

        while True:
            if sha1 not in commits:
                commit = Commit.fromSHA1(db, self, sha1)

                commit_users.add(commit.author)
                commit_users.add(commit.committer)

                if emptydb:
                    commits_values.append(commit)
                    new_commit = True
                else:
                    cursor.execute("""SELECT id
                                        FROM commits
                                       WHERE sha1=%s""",
                                   (commit.sha1,))

                    if not cursor.fetchone():
                        commits_values.append(commit)
                        new_commit = True
                    else:
                        new_commit = False

                commits.add(sha1)

                if new_commit:
                    parents = set(commit.parents)
                    edges_values.extend((parent_sha1, commit.sha1)
                                        for parent_sha1 in parents)
                    stack.extend(parents)

            if not stack:
                break

            sha1 = stack.pop(0)

        with db.updating_cursor("gitusers", "commits", "edges") as cursor:
            commit_user_ids = {}

            for commit_user in commit_users:
                commit_user_ids[commit_user] = commit_user.getOrCreateGitUserId(
                    cursor)

            cursor.executemany(
                """INSERT INTO commits (sha1, author_gituser, commit_gituser,
                                        author_time, commit_time)
                        VALUES (%s, %s, %s, %s, %s)""",
                ((commit.sha1,
                  commit_user_ids[commit.author],
                  commit_user_ids[commit.committer],
                  commit.author.asTimestamp(),
                  commit.committer.asTimestamp())
                 for commit in commits_values))

            cursor.executemany(
                """INSERT INTO edges (parent, child)
                        SELECT parents.id, children.id
                          FROM commits AS parents,
                               commits AS children
                         WHERE parents.sha1=%s
                           AND children.sha1=%s""",
                edges_values)

    def createTag(self, db, name, tagged_sha1):
        # The "tagged" SHA-1 might reference an annotated tag object, so make
        # sure to convert it into a commit SHA-1 before continuing.
        sha1 = self.run("rev-parse", "--verify", "--quiet",
                        tagged_sha1 + "^{commit}").strip()

        with db.updating_cursor("tags") as cursor:
            cursor.execute("""INSERT INTO tags (name, repository, sha1)
                                   VALUES (%s, %s, %s)""",
                           (name, self.id, sha1))

    def updateTag(self, db, name, old_tagged_sha1, new_tagged_sha1):
        # The "tagged" SHA-1 might reference an annotated tag object, so make
        # sure to convert it into a commit SHA-1 before continuing.
        new_sha1 = self.run("rev-parse", "--verify", "--quiet",
                            new_tagged_sha1 + "^{commit}").strip()

        with db.updating_cursor("tags") as cursor:
            cursor.execute("""UPDATE tags
                                 SET sha1=%s
                               WHERE name=%s
                                 AND repository=%s""",
                           (new_sha1, name, self.id))

    def deleteTag(self, db, name):
        with db.updating_cursor("tags") as cursor:
            cursor.execute("""DELETE
                                FROM tags
                               WHERE name=%s
                                 AND repository=%s""",
                           (name, self.id))

class CommitUserTime(object):
    def __init__(self, name, email, time):
        self.name = name
        self.email = email
        self.time = time

    def __hash__(self):
        return hash((self.name, self.email))

    def __eq__(self, other):
        return self.name == other.name and self.email == other.email

    def __getIds(self, db):
        cache = db.storage["CommitUserTime"]
        cache_key = (self.name, self.email)

        if cache_key not in cache:
            cursor = db.readonly_cursor()
            cursor.execute("""SELECT id
                                FROM gitusers
                               WHERE fullname=%s
                                 AND email=%s""",
                           (self.name, self.email))
            row = cursor.fetchone()
            if not row:
                with db.updating_cursor("gitusers") as cursor:
                    cursor.execute("""INSERT INTO gitusers (fullname, email)
                                           VALUES (%s, %s)
                                        RETURNING id""",
                                   (self.name, self.email))
                    row = cursor.fetchone()
            gituser_id, = row

            cursor = db.readonly_cursor()
            cursor.execute("""SELECT uid
                                FROM usergitemails
                               WHERE email=%s""",
                           (self.email,))
            user_ids = frozenset(user_id for user_id, in cursor)

            cache[cache_key] = user_ids, gituser_id

        return cache.get(cache_key)

    def getUserIds(self, db):
        return self.__getIds(db)[0]

    def getGitUserId(self, db):
        return self.__getIds(db)[1]

    def getOrCreateGitUserId(self, cursor):
        cursor.execute("""SELECT id
                            FROM gitusers
                           WHERE fullname=%s
                             AND email=%s""",
                       (self.name, self.email))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""INSERT INTO gitusers (fullname, email)
                                   VALUES (%s, %s)
                                RETURNING id""",
                           (self.name, self.email))
            row = cursor.fetchone()
        gituser_id, = row
        return gituser_id

    def getFullname(self, db):
        user_ids = self.getUserIds(db)
        if len(user_ids) == 1:
            import dbutils
            return dbutils.User.fromId(db, tuple(user_ids)[0]).fullname
        else:
            return self.name

    def asTimestamp(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", self.time)

    def __str__(self):
        return "%s <%s> at %s" % (self.name, self.email, self.asTimestamp())

    @staticmethod
    def fromValue(value):
        match = re_author_committer.match(value)
        return CommitUserTime(textutils.decode(match.group(1)).encode("utf-8"),
                              textutils.decode(match.group(2)).encode("utf-8"),
                              time.gmtime(int(match.group(3).split(" ")[0])))

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
        self.__treeCache = {}

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

        message = textutils.decode(data).encode("utf-8")

        commit = Commit(repository, commit_id, gitobject.sha1, parents, author,
                        committer, message, tree)
        commit.__cache(db)
        return commit

    @staticmethod
    def fromSHA1(db, repository, sha1, commit_id=None):
        return Commit.fromGitObject(db, repository, repository.fetch(sha1), commit_id)

    @staticmethod
    def fromId(db, repository, commit_id):
        commit = db.storage["Commit"].get(commit_id)
        if not commit:
            cursor = db.readonly_cursor()
            cursor.execute("SELECT sha1 FROM commits WHERE id=%s", (commit_id,))
            sha1 = cursor.fetchone()[0]
            commit = Commit.fromSHA1(db, repository, sha1, commit_id)
        return commit

    @staticmethod
    def fromAPI(api_commit):
        return Commit.fromSHA1(api_commit.critic.database,
                               Repository.fromAPI(api_commit.repository),
                               api_commit.sha1, api_commit.id)

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

    def niceSummary(self, include_tag=True):
        try:
            summary, _, rest = self.message.partition("\n")

            if summary.startswith("fixup! ") or summary.startswith("squash! "):
                fixup_summary = rest.strip().partition("\n")[0].strip()
                if fixup_summary:
                    what = summary[:summary.index("!")]
                    if include_tag:
                        return "[%s] %s" % (what, fixup_summary)
                    else:
                        return fixup_summary

            return summary
        except:
            return self.summary()

    def getId(self, db):
        if self.id is None:
            cursor = db.readonly_cursor()
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

    def oneline(self, db, decorate=False):
        line = "%s %s" % (self.sha1[:8], self.niceSummary())
        if decorate:
            decorations = []
            if self == self.repository.getHead(db):
                decorations.append("HEAD")
            cursor = db.readonly_cursor()
            cursor.execute("""SELECT branches.name
                                FROM branches
                                JOIN branchcommits ON (branchcommits.branch=branches.id)
                                JOIN commits ON (commits.id=branchcommits.commit)
                               WHERE commits.sha1=%s""",
                           (self.sha1,))
            decorations.extend(branch for (branch,) in cursor)
            if decorations:
                line += " (%s)" % ", ".join(decorations)
        return line

    def isAncestorOf(self, other):
        if isinstance(other, Commit):
            if self.repository != other.repository:
                return False
            other_sha1 = other.sha1
        else:
            other_sha1 = str(other)

        try:
            self.repository.run(
                "merge-base", "--is-ancestor", self.sha1, other_sha1)
        except GitCommandError:
            # Non-zero exit status means "not ancestor of".  It might also mean
            # failure to calculate somehow, like for instance "invalid SHA-1",
            # but that most likely also means "not ancestor of" in practice.
            return False
        else:
            # Zero exit status means "ancestor of".
            return True

    def getTree(self, path):
        path = "/" + path.lstrip("/")
        if path not in self.__treeCache:
            self.__treeCache[path] = Tree.fromPath(self, path)
        return self.__treeCache[path]

    def getFileEntry(self, path):
        tree = self.getTree(os.path.dirname(path))
        if tree is None:
            return None
        return tree.get(os.path.basename(path))

    def getFileSHA1(self, path):
        entry = self.getFileEntry(path)
        if entry is None:
            return None
        return entry.sha1

    def isDirectory(self, path):
        return self.getTree(path) is not None

RE_LSTREE_LINE = re.compile(
    "(?P<mode>[0-9]{6}) (?P<type>blob|tree|commit) (?P<sha1>[0-9a-f]{40}) +"
    "(?P<size>[0-9]+|-)\t(?P<quote>[\"']?)(?P<name>.*)(?P=quote)$")

class Tree:
    class Entry:
        class Mode(int):
            def __new__(cls, value):
                return super(Tree.Entry.Mode, cls).__new__(cls, int(value, 8))

            def __str__(self):
                if stat.S_ISDIR(self):
                    return "d---------"
                elif self == 0o160000:
                    return "m---------"
                else:
                    if stat.S_ISLNK(self): string = "l"
                    else: string = "-"

                    flags = ["---", "--x", "-w-", "-wx", "r--", "r-x", "rw-", "rwx"]
                    return string + flags[(self & 0o700) >> 6] + flags[(self & 0o70) >> 3] + flags[self & 0o7]

        def __init__(self, name, mode, type, sha1, size):
            if len(name) > 2 and name[0] in ('"', "'") and name[-1] == name[0]:
                name = diff.parse.demunge(name[1:-1])

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
        if isinstance(item, int):
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

        try:
            lstree_output = commit.repository.run("ls-tree", "-l", what)
        except GitCommandError as error:
            if error.output == "fatal: Not a valid object name %s" % what:
                return None
            raise

        for line in lstree_output.splitlines():
            match = RE_LSTREE_LINE.match(line)

            assert match, "Unexpected output from 'git ls-tree': %r" % line

            name = match.group("name")
            if match.group("quote"):
                name = diff.parse.demunge(name)

            if match.group("type") == "blob":
                size = int(match.group("size"))
            else:
                size = None

            entries.append(Tree.Entry(name=name,
                                      mode=match.group("mode"),
                                      type=match.group("type"),
                                      sha1=match.group("sha1"),
                                      size=size))

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
            batch = subprocess.Popen(
                [configuration.executables.GIT, 'cat-file', '--batch'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, cwd=self.repository.path)

            stdout, stderr = batch.communicate("\n".join(self.sha1s.keys()) + "\n")

            gitobjects = []

            for sha1, commit_id in self.sha1s.items():
                line, stdout = stdout.split("\n", 1)

                try:
                    object_sha1, object_type, object_size = line.split(" ")
                except ValueError:
                    raise SyntaxError("unexpected line: %r" % line)

                assert object_sha1 == sha1, "%s != %s" % (object_sha1, sha1)
                assert object_type == "commit"

                object_size = int(object_size)

                object_data = stdout[:object_size]
                stdout = stdout[object_size + 1:]

                gitobjects.append((GitObject(object_sha1, object_type, object_size, object_data), commit_id))

            self.gitobjects = gitobjects
        except Exception:
            self.error = traceback.format_exc()

    def getCommits(self, db):
        self.join()

        for gitobject, commit_id in self.gitobjects:
            Commit.fromGitObject(db, self.repository, gitobject, commit_id)

def emitGitHookOutput(db, pendingrefupdate_id, output, error=None):
    import dbutils
    if pendingrefupdate_id is None:
        return
    if output is not None and not output.strip():
        return
    if error is not None:
        cursor = db.readonly_cursor()
        cursor.execute("""SELECT updater
                            FROM pendingrefupdates
                           WHERE id=%s""",
                       (pendingrefupdate_id,))
        updater_id, = cursor.fetchone()
        if updater_id is not None:
            updater = dbutils.User.fromId(db, updater_id)
        else:
            updater = None
        if not updater or updater.hasRole(db, "developer"):
            output = error
    if pendingrefupdate_id is not None and ((output and output.strip()) or error):
        with db.updating_cursor("pendingrefupdateoutputs") as cursor:
            cursor.execute(
                """INSERT INTO pendingrefupdateoutputs
                                 (pendingrefupdate, output)
                        VALUES (%s, %s)""",
                (pendingrefupdate_id, output))
