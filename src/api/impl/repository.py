# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

import api
import apiobject

import configuration
import dbutils
import gitutils

class Repository(apiobject.APIObject):
    wrapper_class = api.repository.Repository

    def __init__(self, repository_id, name, path):
        self.id = repository_id
        self.name = name
        self.path = path
        self.__internal = None

    def getInternal(self, critic):
        if not self.__internal:
            self.__internal = gitutils.Repository.fromId(
                db=critic.database, repository_id=self.id)
        return self.__internal

    def getURL(self, critic):
        return gitutils.Repository.constructURL(
            critic.database, critic.effective_user.internal, self.path)

    def run(self, *args):
        argv = [configuration.executables.GIT] + list(args)
        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.path)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise api.repository.GitCommandError(
                argv, process.returncode, stdout, stderr)
        return stdout

    def resolveRef(self, ref, expect, short):
        command_line = ["rev-parse", "--verify", "--quiet"]
        if short:
            if isinstance(short, int):
                command_line.append("--short=%d" % short)
            else:
                command_line.append("--short")
        if expect is not None:
            ref += "^{%s}" % expect
        command_line.append(ref)
        try:
            return self.run(*command_line).strip()
        except api.repository.GitCommandError:
            raise api.repository.InvalidRef(ref)

    def listCommits(self, repository, include, exclude, args, paths):
        args = ['rev-list'] + args
        args.extend(commit.sha1 for commit in include)
        args.extend("^" + commit.sha1 for commit in exclude)
        if paths:
            args.append("--")
            args.extend(paths)
        return [api.commit.fetch(repository, sha1=sha1)
                for sha1 in self.run(*args).split()]

    @classmethod
    def create(Repository, critic, repository_id, name, path):
        return Repository(repository_id, name, path).wrap(critic)

def fetch(critic, repository_id, name, path):
    cursor = critic.getDatabaseCursor()
    if repository_id is not None:
        cursor.execute("""SELECT id, name, path
                            FROM repositories
                           WHERE id=%s""",
                       (repository_id,))
    elif name is not None:
        cursor.execute("""SELECT id, name, path
                            FROM repositories
                           WHERE name=%s""",
                       (name,))
    else:
        cursor.execute("""SELECT id, name, path
                            FROM repositories
                           WHERE path=%s""",
                       (path,))
    try:
        return next(Repository.make(critic, cursor))
    except StopIteration:
        if repository_id is not None:
            raise api.repository.InvalidRepositoryId(repository_id)
        elif name is not None:
            raise api.repository.InvalidRepositoryName(name)
        else:
            raise api.repository.InvalidRepositoryPath(path)

def fetchAll(critic):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT id, name, path
                        FROM repositories
                    ORDER BY name""")
    return list(Repository.make(critic, cursor))

def fetchHighlighted(critic, user):
    highlighted = set()

    cursor = critic.getDatabaseCursor()

    cursor.execute("""SELECT DISTINCT repository
                        FROM filters
                       WHERE uid=%s""",
                   (user.id,))
    highlighted.update(repository_id for (repository_id,) in cursor)

    cursor.execute("""SELECT DISTINCT repository
                        FROM branches
                        JOIN reviews ON (reviews.branch=branches.id)
                        JOIN reviewusers ON (reviewusers.review=reviews.id)
                       WHERE reviewusers.uid=%s
                         AND reviewusers.owner""",
                   (user.id,))
    highlighted.update(repository_id for (repository_id,) in cursor)

    cursor.execute("""SELECT id, name, path
                        FROM repositories
                       WHERE id=ANY (%s)
                    ORDER BY name""",
                   (list(highlighted),))
    return list(Repository.make(critic, cursor))
