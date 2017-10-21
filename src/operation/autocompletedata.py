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

import dbutils
import gitutils
import reviewing.filters

from operation import Operation, OperationResult, OperationError, Optional

class GetAutoCompleteData(Operation):
    def __init__(self):
        Operation.__init__(self, { "values": [{"users", "paths"}],
                                   "review_id": Optional(int),
                                   "changeset_ids": Optional([int]) })

    def process(self, db, user, values, review_id=None, changeset_ids=None):
        cursor = db.cursor()
        data = {}

        if "users" in values:
            cursor.execute("SELECT name, fullname FROM users WHERE status!='retired'")
            data["users"] = dict(cursor)

        if "paths" in values:
            if review_id is not None:
                cursor.execute("""SELECT files.path, SUM(reviewfiles.deleted), SUM(reviewfiles.inserted)
                                    FROM files
                                    JOIN reviewfiles ON (reviewfiles.file=files.id)
                                   WHERE reviewfiles.review=%s
                                GROUP BY files.id""",
                               (review_id,))
            elif changeset_ids is not None:
                cursor.execute("""SELECT files.path, SUM(chunks.deleteCount), SUM(chunks.insertCount)
                                    FROM files
                                    JOIN chunks ON (chunks.file=files.id)
                                   WHERE chunks.changeset=ANY (%s)
                                GROUP BY files.id""",
                               (changeset_ids,))
            else:
                raise OperationError("paths requested, but neither review_id nor changeset_ids given")

            paths = {}

            for filename, deleted, inserted in cursor:
                paths[filename] = (0, deleted, inserted)

                components = filename.split("/")
                for index in range(len(components) - 1, 0, -1):
                    directory = "/".join(components[:index]) + "/"
                    nfiles, current_deleted, current_inserted = paths.get(directory, (0, 0, 0))
                    paths[directory] = nfiles + 1, current_deleted + deleted, current_inserted + inserted

            data["paths"] = paths

        return OperationResult(**data)

class GetRepositoryPaths(Operation):
    def __init__(self):
        Operation.__init__(self, { "prefix": str,
                                   "repository_id": Optional(int),
                                   "repository_name": Optional(str) })

    def process(self, db, user, prefix, repository_id=None, repository_name=None):
        if reviewing.filters.hasWildcard(prefix):
            return OperationResult(paths={})

        prefix = reviewing.filters.sanitizePath(prefix)

        if repository_id is not None:
            repository = gitutils.Repository.fromId(db, repository_id)
        else:
            repository = gitutils.Repository.fromName(db, repository_name)

        if repository.isEmpty():
            return OperationResult(paths={})

        paths = {}

        use_prefix = prefix.rpartition("/")[0]

        if use_prefix:
            names = repository.run("ls-tree", "-r", "--name-only", "HEAD", use_prefix).splitlines()
        else:
            names = repository.run("ls-tree", "-r", "--name-only", "HEAD").splitlines()

        def add(path):
            if path.endswith("/"):
                if path not in paths:
                    paths[path] = { "files": 0 }
                paths[path]["files"] += 1
            else:
                paths[path] = {}

        for name in names:
            if not name.startswith(prefix):
                continue

            relname = name[len(prefix):]
            use_prefix = prefix
            if prefix.endswith("/"):
                add(prefix)
            elif relname.startswith("/"):
                add(prefix + "/")
                use_prefix = prefix + "/"
                relname = relname[1:]

            localname, pathsep, _ = relname.partition("/")

            add(use_prefix + localname + pathsep)

        return OperationResult(paths=paths)
