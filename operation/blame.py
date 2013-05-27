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
import itertools
import diff

from operation import Operation, OperationResult, OperationError, Optional
from log.commitset import CommitSet
from changeset.utils import createChangeset
from changeset.load import loadChangesetsForCommits

class LineAnnotator:
    class NotSupported: pass

    def __init__(self, db, parent, child, file_ids=None, commits=None, changeset_cache=None):
        self.parent = parent
        self.child = child
        self.commitset = CommitSet.fromRange(db, parent, child, commits=commits)
        self.changesets = {}

        if not self.commitset: raise LineAnnotator.NotSupported

        commits = []

        if not changeset_cache: changeset_cache = {}

        for commit in self.commitset:
            if len(commit.parents) > 1: raise LineAnnotator.NotSupported

            if commit in changeset_cache:
                self.changesets[commit.sha1] = changeset_cache[commit]
            else:
                commits.append(commit)

        for changeset in loadChangesetsForCommits(db, parent.repository, commits, filtered_file_ids=file_ids):
            self.changesets[changeset.child.sha1] = changeset_cache[changeset.child] = changeset

        for commit in set(self.commitset) - set(self.changesets.keys()):
            changesets = createChangeset(db, None, commit.repository, commit=commit, filtered_file_ids=file_ids, do_highlight=False)
            assert len(changesets) == 1
            self.changesets[commit.sha1] = changeset_cache[commit] = changesets[0]

        self.commits = [parent]
        self.commit_index = { parent.sha1: 0 }

        for commit in self.commitset:
            self.commit_index[commit.sha1] = len(self.commits)
            self.commits.append(commit)

    class Line:
        def __init__(self, sha1, primary):
            self.sha1 = sha1
            self.primary = primary
            self.untouched = True
        def touch(self, sha1):
            if self.untouched:
                self.sha1 = sha1
                self.untouched = False
        def __repr__(self):
            return self.sha1[:8]

    def annotate(self, file_id, first, last, check_user=None):
        offset = first
        count = last - first + 1

        initial_lines = [LineAnnotator.Line(sha1, True) for sha1 in itertools.repeat(self.parent.sha1, count)]
        lines = initial_lines[:]
        commit = self.commitset.getHeads().pop()

        while True:
            changeset = self.changesets[commit.sha1]
            changeset_file = changeset.getFile(file_id)

            if changeset_file:
                changeset_file.loadOldLines()
                changeset_file.loadNewLines()

                offset_delta = 0
                modifications = []

                for chunk in changeset_file.chunks:
                    if chunk.insertEnd() < offset:
                        offset_delta -= chunk.delta()
                        continue

                    if chunk.insert_offset < offset + count:
                        if not chunk.deleted_lines: chunk.deleted_lines = changeset_file.getOldLines(chunk)
                        if not chunk.inserted_lines: chunk.inserted_lines = changeset_file.getNewLines(chunk)

                        for line in chunk.getLines():
                            if line.new_offset < offset:
                                if line.type == line.DELETED:
                                    offset_delta += 1
                                elif line.type == line.INSERTED:
                                    offset_delta -= 1
                            elif line.new_offset < offset + count:
                                if line.type == line.CONTEXT:
                                    pass
                                elif line.type == line.DELETED:
                                    modifications.append((line.new_offset, -1))
                                else:
                                    if line.type == line.INSERTED:
                                        modifications.append((line.new_offset, 1))
                                    line = lines[line.new_offset - offset]
                                    if check_user and line.primary and line.untouched and commit.author.email == check_user.email:
                                        return True
                                    line.touch(commit.sha1)
                            else:
                                break

                modification_offset = offset

                for line_offset, delta in modifications:
                    if delta > 0:
                        del lines[line_offset - modification_offset]
                        count -= 1
                        modification_offset += 1
                    else:
                        lines.insert(line_offset - modification_offset, LineAnnotator.Line(None, False))
                        count += 1
                        modification_offset -= 1

                offset += offset_delta

            parents = self.commitset.getParents(commit)

            if len(parents) > 1: raise LineAnnotator.NotSupported

            if parents: commit = parents.pop()
            else: break

        if check_user:
            if self.parent.author.email == check_user.email:
                return any(itertools.imap(lambda line: line.untouched, initial_lines))
            else:
                return False
        else:
            return [(first + index, self.commit_index[line.sha1]) for index, line in enumerate(initial_lines)]

class Blame(Operation):
    def __init__(self):
        Operation.__init__(self, { "repository_id": int,
                                   "changeset_id": int,
                                   "files": [{ "id": int,
                                               "blocks": [{ "first": int,
                                                            "last": int }]
                                               }]
                                   })

    def process(self, db, user, repository_id, changeset_id, files):
        repository = gitutils.Repository.fromId(db, repository_id)

        cursor = db.cursor()
        cursor.execute("SELECT parent, child FROM changesets WHERE id=%s", (changeset_id,))

        parent_id, child_id = cursor.fetchone()
        parent = gitutils.Commit.fromId(db, repository, parent_id)
        child = gitutils.Commit.fromId(db, repository, child_id)

        try:
            annotator = LineAnnotator(db, parent, child)

            for file in files:
                for block in file["blocks"]:
                    lines = annotator.annotate(file["id"], block["first"], block["last"])
                    block["lines"] = [{ "offset": offset, "commit": commit } for offset, commit in lines]

            return OperationResult(commits=[{ "sha1": commit.sha1,
                                              "author_name": commit.author.name,
                                              "author_email": commit.author.email,
                                              "summary": commit.niceSummary(),
                                              "message": commit.message,
                                              "original": commit == parent,
                                              "current": commit == child }
                                            for commit in annotator.commits],
                                   files=files)
        except LineAnnotator.NotSupported:
            blame = gitutils.Blame(parent, child)

            paths = {}

            for file in files:
                file_id = file["id"]

                path = paths.get(file_id)

                if not path:
                    path = paths[file_id] = dbutils.describe_file(db, file_id)

                for block in file["blocks"]:
                    block["lines"] = blame.blame(db, path, block["first"], block["last"])

            return OperationResult(commits=blame.commits, files=files)
