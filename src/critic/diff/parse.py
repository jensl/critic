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

import asyncio
import re
from typing import (
    Dict,
    List,
    Literal,
    Mapping,
    NamedTuple,
    Sequence,
    Tuple,
    Union,
    overload,
)

from critic import diff
from critic import gitaccess
from critic import textutils
from critic.gitaccess import SHA1


def splitlines(source, *, limit=None):
    if isinstance(source, bytes):
        source = textutils.decode(source)

    if not source:
        return source

    args = []
    if limit is not None:
        args.append(int(limit))

    if source[-1] == "\n":
        lines = source[:-1].split("\n", *args)
    else:
        lines = source.split("\n", *args)

    if limit is not None:
        return lines[:limit]

    return lines


ExamineResult = Union[None, Literal["binary"], int]


async def examine_file(
    repository: gitaccess.GitRepository, commit: SHA1, path: str
) -> ExamineResult:
    return (await examine_files(repository, commit, [path]))[0]


@overload
async def examine_files(
    repository: gitaccess.GitRepository, commit: SHA1, paths: Sequence[str]
) -> Sequence[ExamineResult]:
    ...


@overload
async def examine_files(
    repository: gitaccess.GitRepository,
    commit: SHA1,
    paths: Mapping[str, ExamineResult],
) -> Mapping[str, ExamineResult]:
    ...


async def examine_files(
    repository: gitaccess.GitRepository,
    commit: SHA1,
    paths: Union[Sequence[str], Mapping[str, ExamineResult]],
) -> Union[Sequence[ExamineResult], Mapping[str, ExamineResult]]:
    """Basic check of file version at |paths| in |commit|

    The result per path is either None, if the file doesn't exist, or "binary"
    if it is a binary file (according to Git,) and otherwise the number of lines
    in the file.

    If |paths| is a list, the return value is a list, in the same order, with
    the result for each path.  If |paths| is a dict its keys are used as paths,
    and the return value is that same dict with each value replaced with result
    for each key/path."""

    argv = [
        "diff-tree",
        # "recurse into sub-trees"  Without this, the command will always just
        # say "the top-level directory (containing the file) was added".
        "-r",
        # Disable path name munging, and use NUL as field separator.
        "-z",
        # Gives us number of lines, or "-" for binary files.
        "--numstat",
        gitaccess.EMPTY_TREE_SHA1,
        commit,
        "--",
        *paths,
    ]

    output = textutils.decode(await repository.run(*argv)).rstrip("\0")
    per_path: Dict[str, ExamineResult] = {}

    for line in output.split("\0"):
        if not line:
            continue
        added, removed, path = line.split("\t", 2)
        # We're comparing to the empty tree, so all files should appear as newly
        # added (or possibly binary.)
        assert removed in ("0", "-")
        if added == "-":
            per_path[path] = "binary"
        else:
            per_path[path] = int(added)

    # Paths we ask about might be missing (because no such file existed) but we
    # should not receive information about any paths we didn't ask for.
    assert not set(per_path) - set(paths), repr((argv, set(per_path) - set(paths)))

    if isinstance(paths, list):
        return [per_path.get(path) for path in paths]

    return {path: per_path.get(path) for path in paths}


class ParseError(Exception):
    pass


RE_HUNK_HEADER = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
RE_WHITESPACE = re.compile(r"\s+")

# Indexes into the 6-tuples returned and processed by the functions below.
OLD_OFFSET = 0
OLD_COUNT = 1
OLD_LENGTH = 2
NEW_OFFSET = 3
NEW_COUNT = 4
NEW_LENGTH = 5


async def basic_file_difference(repository, from_commit, to_commit, path):
    """Run 'git diff-tree' and parse the output

       The return value is a tuple

         (old_file_sha1, new_file_sha1, blocks)

       where |blocks| is a generator producing a tuple

         (delete_offset, delete_count, delete_length,
          insert_offset, insert_count, insert_length)

       for each individual block of changed lines.  The *_count and *_length
       items in these tuples are always identical."""

    argv = [
        "diff-tree",
        # Unified diff with no context.
        "--unified=0",
        # "Patience" algorithm; might be nicer.
        "--patience",
        # Unabbreviated SHA-1 sums.
        "--full-index",
        # Ignore space changes (we detect them separately, for a nicer diff.)
        "--ignore-space-change",
        str(from_commit),
        str(to_commit),
        "--",
        path,
    ]

    async def get_file_sha1(commit, path):
        return await repository.revparse(f"{commit}:{path}")

    old_file_sha1 = await get_file_sha1(from_commit, path)
    new_file_sha1 = await get_file_sha1(to_commit, path)

    diff = textutils.decode(await repository.run(*argv))

    if not diff:
        # Empty diff => white-space only changes.
        return old_file_sha1, new_file_sha1, iter([])

    diff_lines = iter(splitlines(diff))
    first_hunk_header = None

    try:
        while True:
            diff_line = next(diff_lines)

            if diff_line.startswith("index "):
                file_sha1s = diff_line[6:].split(None, 1)[0]
                if file_sha1s.split("..") != [old_file_sha1, new_file_sha1]:
                    raise ParseError("unexpected SHA-1 sums: %r" % diff_line)
                continue
            elif diff_line.startswith("@@ "):
                match = RE_HUNK_HEADER.match(diff_line)
                if not match:
                    raise ParseError("malformed hunk header: " + diff_line)
                first_hunk_header = match.groups()
                break
    except StopIteration:
        raise ParseError("EOF while scanning for first hunk header: %r" % diff)

    if old_file_sha1 is None or new_file_sha1 is None:
        raise ParseError("no 'index' line encountered")

    def blocks(hunk_header):
        def check_hunk():
            if delete_count == insert_count == 0:
                raise ParseError("empty hunk")
            if delete_count != delete_length or insert_count != insert_length:
                raise ParseError("hunk header and hunk don't match")

        try:
            while True:
                (
                    delete_offset,
                    delete_length,
                    insert_offset,
                    insert_length,
                ) = hunk_header

                delete_offset = int(delete_offset)
                insert_offset = int(insert_offset)

                if delete_length is None:
                    delete_length = 1
                else:
                    delete_length = int(delete_length)
                if insert_length is None:
                    insert_length = 1
                else:
                    insert_length = int(insert_length)

                # We use zero-based offsets, hunk headers use one-based ones, so
                # adjust.
                #
                # Note: due to unified diff format madness, zero-length hunk
                # sides (i.e. the other side of hunks that only delete or add
                # lines) have a zero-based offset, for no apparent reason.
                if delete_length != 0:
                    delete_offset -= 1
                if insert_length != 0:
                    insert_offset -= 1

                delete_count = insert_count = 0

                while True:
                    line = next(diff_lines)

                    if line[0] == "-":
                        delete_count += 1
                    elif line[0] == "+":
                        insert_count += 1
                    elif line[0] == "@":
                        check_hunk()
                        yield (
                            delete_offset,
                            delete_count,
                            delete_count,
                            insert_offset,
                            insert_count,
                            insert_count,
                        )
                        match = RE_HUNK_HEADER.match(line)
                        if not match:
                            raise ParseError("malformed hunk header: " + line)
                        hunk_header = match.groups()
                        break
                    elif line[0] == "\\":
                        # Typically "No newline at end of file".
                        continue
                    else:
                        raise ParseError("unexpected line: " + line)
        except StopIteration:
            check_hunk()
            yield (
                delete_offset,
                delete_count,
                delete_count,
                insert_offset,
                insert_count,
                insert_count,
            )

    return old_file_sha1, new_file_sha1, blocks(first_hunk_header)


def whitespace_difference(old_lines, old_offset, new_lines, new_offset, length):
    """Detect white-space differences in context lines

       This function returns a generator of 6-tuples, like the tuples returned
       by |basic_file_difference()|.

       Note: This function doesn't really just detect white-space
       differences; it detects any and all differences in context lines.  It
       is only used to detect white-space differences, however."""

    delete_offset = insert_offset = None
    count = 0

    while length:
        if old_lines[old_offset] != new_lines[new_offset]:
            if count == 0:
                delete_offset = old_offset
                insert_offset = new_offset
            count += 1
        elif count != 0:
            yield (delete_offset, count, count, insert_offset, count, count)
            count = 0

        old_offset += 1
        new_offset += 1
        length -= 1

    if count != 0:
        yield (delete_offset, count, count, insert_offset, count, count)


def with_whitespace_difference(old_lines, new_lines, blocks):
    """Augment a list of block (6-tuples) with white-space changes between them

       Iterate over the individual blocks in |blocks| and examine the context
       lines between for white-space only changes, and insert additional blocks
       into the returned sequence of blocks.

       This is only necessary because we call 'git diff-tree' with the
       '--ignore-space-change' option.  We do that to achieve a better final
       result when large blocks of code are re-indented, by having the main
       (clever) diff algorithm (the one in 'git diff-tree') focus on actual
       changes.  We can deal with the white-space changes ourselves.

       The return value is a generator of blocks (6-tuples).

       The |old_lines| and |new_lines| arguments should be lists containing all
       lines in the old and new versions of the file."""

    def whitespace_between(prev_block, next_block):
        old_offset = prev_block[OLD_OFFSET] + prev_block[OLD_LENGTH]
        new_offset = prev_block[NEW_OFFSET] + prev_block[NEW_LENGTH]
        length = next_block[OLD_OFFSET] - old_offset
        assert length == next_block[NEW_OFFSET] - new_offset, (prev_block, next_block)
        return whitespace_difference(
            old_lines, old_offset, new_lines, new_offset, length
        )

    head_block = (0, 0, 0, 0, 0, 0)
    tail_block = (len(old_lines), 0, 0, len(new_lines), 0, 0)

    # Note: In case of white-space only changes, blocks will be empty.
    try:
        prev_block = next(blocks)
    except StopIteration:
        whitespace_blocks = whitespace_between(head_block, tail_block)
        # Call next() explicitly once, to trigger an exception if we didn't find
        # at least one.
        yield next(whitespace_blocks)
        for whitespace_block in whitespace_blocks:
            yield whitespace_block
        return

    for whitespace_block in whitespace_between(head_block, prev_block):
        yield whitespace_block

    yield prev_block

    for next_block in blocks:
        for whitespace_block in whitespace_between(prev_block, next_block):
            yield whitespace_block
        yield next_block
        prev_block = next_block

    for whitespace_block in whitespace_between(prev_block, tail_block):
        yield whitespace_block


def merged_block(prev_block, next_block, context_between=0):
    assert context_between == next_block[OLD_OFFSET] - (
        prev_block[OLD_OFFSET] + prev_block[OLD_LENGTH]
    )
    return (
        prev_block[OLD_OFFSET],
        prev_block[OLD_COUNT] + next_block[OLD_COUNT],
        prev_block[OLD_LENGTH] + context_between + next_block[OLD_LENGTH],
        prev_block[NEW_OFFSET],
        prev_block[NEW_COUNT] + next_block[NEW_COUNT],
        prev_block[NEW_LENGTH] + context_between + next_block[NEW_LENGTH],
    )


def with_merged_adjacent(blocks):
    """Merge adjacent blocks (6-tuples) in |blocks|

       The return value is a generator of blocks (6-tuples)."""

    # Note: There must necessarily be at least one block.
    prev_block = next(blocks)

    for next_block in blocks:
        # We only need to compare one side, since there must be an equal
        # number of context lines between blocks on both sides.
        prev_old_end = prev_block[OLD_OFFSET] + prev_block[OLD_LENGTH]
        if prev_old_end == next_block[OLD_OFFSET]:
            prev_block = merged_block(prev_block, next_block)
        else:
            yield prev_block
            prev_block = next_block

    yield prev_block


# Maximum number of context lines with_false_splits_merged() will consider as
# potentially a false split.  Blocks separated by more context lines than this
# are never split.
FALSE_SPLIT_MAX_CONTEXT = 3


def with_false_splits_merged(old_lines, new_lines, blocks):
    """Merge blocks in |blocks| separated by insignificant context lines

       A context line is heuristically determined to be insignificant by
       observing whether at least one identical (modulo white-space) line exists
       in either the preceding or following block.

       This is done to avoid blocks being split into two by "false" matches on
       common, insignificant lines.  Such splits are detrimental since our
       intra-block alignment code only looks at one block at a time, and can't
       align lines from different blocks.

       The return value is a generator of blocks (6-tuples).

       The |old_lines| and |new_lines| arguments should be lists containing all
       lines in the old and new versions of the file."""

    # Note: There must necessarily be at least one block.
    prev_block = next(blocks)

    for next_block in blocks:
        old_context_offset = prev_block[OLD_LENGTH]
        new_context_offset = prev_block[NEW_LENGTH]

        old_context_end = next_block[OLD_OFFSET] - prev_block[OLD_OFFSET]
        context_between = old_context_end - old_context_offset
        if context_between > FALSE_SPLIT_MAX_CONTEXT:
            yield prev_block
            prev_block = next_block
            continue

        old_begin = prev_block[OLD_OFFSET]
        old_end = next_block[OLD_OFFSET] + next_block[OLD_LENGTH]
        old_counted = diff.analyze.Lines(old_lines[old_begin:old_end])
        new_begin = prev_block[NEW_OFFSET]
        new_end = next_block[NEW_OFFSET] + next_block[NEW_LENGTH]
        new_counted = diff.analyze.Lines(new_lines[new_begin:new_end])

        for index in range(context_between):
            if not (
                old_counted.count(old_context_offset + index) > 1
                or new_counted.count(new_context_offset + index) > 1
            ):
                yield prev_block
                prev_block = next_block
                break
        else:
            prev_block = merged_block(prev_block, next_block, context_between)

    yield prev_block


class DiffBlock(NamedTuple):
    index_: int
    offset: int
    delete_offset: int
    delete_count: int
    delete_length: int
    insert_offset: int
    insert_count: int
    insert_length: int


class FileDifference(NamedTuple):
    blocks: Sequence[DiffBlock]
    old_linebreak: bool
    new_linebreak: bool


async def file_difference(
    repository: gitaccess.GitRepository, from_commit: SHA1, to_commit: SHA1, path: str,
) -> FileDifference:
    """Parse differences in a file between two commits

       Differences are returned as a list of tuples of six (8) values:

         (index, offset,
          delete_offset, delete_count, delete_length,
          insert_offset, insert_count, insert_length)

       Calling this function is only meaningful when the named file exists in
       both commits, and when it isn't a binary file in either, and when it has
       been changed.

       Added, removed and/or binary files, are handled elsewhere."""

    old_file_sha1, new_file_sha1, blocks = await basic_file_difference(
        repository, from_commit, to_commit, path
    )

    def fetch_lines(blob):
        """Fetch file blob from repository and split into lines"""
        linebreak = blob.data.endswith(b"\n")
        return splitlines(blob.data), linebreak

    old_blob, new_blob = await repository.fetchall(
        old_file_sha1, new_file_sha1, wanted_object_type="blob"
    )
    old_lines, old_linebreak = fetch_lines(old_blob)
    new_lines, new_linebreak = fetch_lines(new_blob)

    # Complete the list of blocks by inserting additional blocks for white-space
    # only changes in the "context" between blocks (or before the first, or
    # after the last.)
    blocks = with_whitespace_difference(old_lines, new_lines, blocks)

    # The step above might have introduced adjacent blocks in the list, so merge
    # those.
    blocks = with_merged_adjacent(blocks)

    # To improve our subsequent analysis of the difference, merge blocks that
    # are only separated by a few insignificant context lines.
    blocks = with_false_splits_merged(old_lines, new_lines, blocks)

    # Return the result.  Since |blocks| is a (nested) generator, this is where
    # everything actually happens.
    old_offset = new_offset = 0
    result: List[DiffBlock] = []
    for (
        delete_offset,
        delete_count,
        delete_length,
        insert_offset,
        insert_count,
        insert_length,
    ) in blocks:
        offset = delete_offset - old_offset
        assert offset == insert_offset - new_offset
        result.append(
            DiffBlock(
                len(result),
                offset,
                delete_offset,
                delete_count,
                delete_length,
                insert_offset,
                insert_count,
                insert_length,
            )
        )
        old_offset = delete_offset + delete_length
        new_offset = insert_offset + insert_length
        # Yield to the event loop.
        await asyncio.sleep(0)
    return FileDifference(result, old_linebreak, new_linebreak)
