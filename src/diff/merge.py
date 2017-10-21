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

import diff
import diff.parse
import gitutils

# Maximum number of lines allowed between a two chunks to consider
# them near enough to warrant inclusion.
PROXIMITY_LIMIT = 3

def filterChunks(log, file_on_branch, file_in_merge, path):
    """filterChunks([diff.Chunk, ...], [diff.Chunk, ...]) => [diff.Chunk, ...]

    Filter the second list of chunks to only include chunks that affect lines
    that are within PROXIMITY_LIMIT lines of a chunk in the first list of
    chunks."""

    result = []

    on_branch = iter(file_on_branch.chunks)
    in_merge = iter(file_in_merge.chunks)

    try:
        chunk_on_branch = next(on_branch)
        chunk_in_merge = next(in_merge)

        while True:
            if chunk_in_merge.delete_offset - chunk_on_branch.insertEnd() > PROXIMITY_LIMIT:
                # Chunk_on_branch is significantly earlier than chunk_in_merge,
                # so continue to next one from on_branch.
                chunk_on_branch = next(on_branch)
            elif chunk_on_branch.insert_offset - chunk_in_merge.deleteEnd() > PROXIMITY_LIMIT:
                chunk_in_merge = next(in_merge)
            else:
                # The two chunks are near each other, or intersects, so include
                # the one from the merge
                result.append(chunk_in_merge)

                # ... and continue to the next one from in_merge.
                chunk_in_merge = next(in_merge)
    except StopIteration:
        # We ran out of chunks from either on_branch or in_merge.  If we ran out
        # of chunks from in_merge, we obviously don't need to include any more
        # chunks in the result.  If we ran out of chunks from on_branch, we
        # don't either, because the previous one was apparently significant
        # earlier than the current, and thus all following, chunks from in_merge.
        pass

    return result

def parseMergeDifferences(db, repository, commit):
    mergebase = gitutils.Commit.fromSHA1(db, repository, repository.mergebase(commit, db=db))

    result = {}
    log = [""]

    for parent_sha1 in commit.parents:
        parent = gitutils.Commit.fromSHA1(db, repository, parent_sha1)

        if parent_sha1 == mergebase:
            result[parent_sha1] = diff.parse.parseDifferences(repository, from_commit=parent, to_commit=commit)[parent_sha1]
        else:
            paths_on_branch = set(repository.run('diff', '--name-only', "%s..%s" % (mergebase, parent)).splitlines())
            paths_in_merge = set(repository.run('diff', '--name-only', "%s..%s" % (parent, commit)).splitlines())

            filter_paths = paths_on_branch & paths_in_merge

            on_branch = diff.parse.parseDifferences(repository, from_commit=mergebase, to_commit=parent, filter_paths=filter_paths)[mergebase.sha1]
            in_merge = diff.parse.parseDifferences(repository, from_commit=parent, to_commit=commit, filter_paths=filter_paths)[parent_sha1]

            files_on_branch = dict([(file.path, file) for file in on_branch])

            result_for_parent = []

            for file_in_merge in in_merge:
                file_on_branch = files_on_branch.get(file_in_merge.path)
                if file_on_branch:
                    filtered_chunks = filterChunks(log, file_on_branch, file_in_merge, file_in_merge.path)

                    if filtered_chunks:
                        result_for_parent.append(diff.File(id=None,
                                                           repository=repository,
                                                           path=file_in_merge.path,
                                                           old_sha1=file_in_merge.old_sha1,
                                                           new_sha1=file_in_merge.new_sha1,
                                                           old_mode=file_in_merge.old_mode,
                                                           new_mode=file_in_merge.new_mode,
                                                           chunks=filtered_chunks))

            result[parent_sha1] = result_for_parent

    return result
