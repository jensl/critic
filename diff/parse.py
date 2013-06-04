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

import configuration
import subprocess
import gitutils
import diff
import re
import itertools
import analyze

GIT_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

def demunge(path):
    special = { "a": "\a",
                "b": "\b",
                "t": "\t",
                "n": "\n",
                "v": "\v",
                "f": "\f",
                "r": "\r",
                '"': '"',
                "'": "'",
                "/": "/",
                "\\": "\\" }

    def unescape(match):
        escaped = match.group(1)
        if escaped in special:
            return special[escaped]
        else:
            return chr(int(escaped, 8))

    return re.sub(r"""\\([abtnvfr"'/\\]|[0-9]{3})""", unescape, path)

def splitlines(source):
    if not source: return source
    elif source[-1] == "\n": return source[:-1].split("\n")
    else: return source.split("\n")

def detectWhiteSpaceChanges(file, old_lines, begin_old_offset, end_old_offset, old_ending_linebreak, new_lines, begin_new_offset, end_new_offset, new_ending_linebreak):
    start_old_offset = None

    for old_offset, new_offset in itertools.izip(xrange(begin_old_offset, end_old_offset), xrange(begin_new_offset, end_new_offset)):
        if old_lines[old_offset - 1] != new_lines[new_offset - 1] or (old_offset == len(old_lines) and old_ending_linebreak != new_ending_linebreak):
            if start_old_offset is None:
                start_old_offset = old_offset
                start_new_offset = new_offset
        elif start_old_offset is not None:
            assert old_offset - start_old_offset != 0 and new_offset - start_new_offset != 0
            chunk = diff.Chunk(start_old_offset, old_offset - start_old_offset,
                               start_new_offset, new_offset - start_new_offset,
                               is_whitespace=True)
            chunk.is_whitespace = True
            file.chunks.append(chunk)
            start_old_offset = None

    if start_old_offset is not None:
        assert end_old_offset - start_old_offset != 0 and end_new_offset - start_new_offset != 0
        chunk = diff.Chunk(start_old_offset, end_old_offset - start_old_offset,
                           start_new_offset, end_new_offset - start_new_offset,
                           is_whitespace=True)
        chunk.is_whitespace = True
        file.chunks.append(chunk)

ws = re.compile("\\s+")

def isWhitespaceChange(deleted_line, inserted_line):
    return ws.sub(" ", deleted_line.strip()) == ws.sub(" ", inserted_line.strip())

def createChunks(delete_offset, deleted_lines, insert_offset, inserted_lines):
    ws_before = None
    ws_after = None

    if deleted_lines and inserted_lines and isWhitespaceChange(deleted_lines[0], inserted_lines[0]):
        ws_lines = 1
        max_lines = min(len(deleted_lines), len(inserted_lines))

        while ws_lines < max_lines and isWhitespaceChange(deleted_lines[ws_lines], inserted_lines[ws_lines]):
            ws_lines += 1

        ws_before = diff.Chunk(delete_offset, ws_lines, insert_offset, ws_lines, is_whitespace=True)

        delete_offset += ws_lines
        del deleted_lines[:ws_lines]

        insert_offset += ws_lines
        del inserted_lines[:ws_lines]

    if deleted_lines and inserted_lines and isWhitespaceChange(deleted_lines[-1], inserted_lines[-1]):
        ws_lines = 1
        max_lines = min(len(deleted_lines), len(inserted_lines))

        while ws_lines < max_lines and isWhitespaceChange(deleted_lines[-(ws_lines + 1)], inserted_lines[-(ws_lines + 1)]):
            ws_lines += 1

        ws_after = diff.Chunk(delete_offset + len(deleted_lines) - ws_lines, ws_lines,
                              insert_offset + len(inserted_lines) - ws_lines, ws_lines,
                              is_whitespace=True)

        del deleted_lines[-ws_lines:]
        del inserted_lines[-ws_lines:]

    if deleted_lines or inserted_lines:
        chunks = [diff.Chunk(delete_offset, len(deleted_lines), insert_offset, len(inserted_lines))]
    else:
        chunks = []

    if ws_before: chunks.insert(0, ws_before)
    if ws_after: chunks.append(ws_after)

    return chunks

def mergeChunks(file):
    if len(file.chunks) > 1:
        file.loadOldLines(False)
        old_lines = file.oldLines(False)
        file.loadNewLines(False)
        new_lines = file.newLines(False)

        merged = []
        previous = file.chunks[0]

        for chunk in file.chunks[1:]:
            assert previous.delete_count != 0 or previous.insert_count != 0

            offset = previous.delete_offset + previous.delete_count

            while offset < chunk.delete_offset:
                if not analyze.re_ignore.match(old_lines[offset - 1]):
                    break
                offset += 1
            else:
                previous.delete_count = (chunk.delete_offset - previous.delete_offset) + chunk.delete_count
                previous.insert_count = (chunk.insert_offset - previous.insert_offset) + chunk.insert_count

                assert previous.delete_count != 0 or previous.insert_count != 0

                previous.is_whitespace = previous.is_whitespace and chunk.is_whitespace
                continue

            merged.append(previous)
            previous = chunk

        merged.append(previous)

        for chunk in merged:
            while chunk.insert_count > 1 and chunk.delete_count > 1:
                insert_last = new_lines[chunk.insert_offset + chunk.insert_count - 2]
                delete_last = old_lines[chunk.delete_offset + chunk.delete_count - 2]

                if insert_last == delete_last:
                    chunk.delete_count -= 1
                    chunk.insert_count -= 1
                else:
                    break

        file.clean()
        file.chunks = merged

def parseDifferences(repository, commit=None, from_commit=None, to_commit=None, filter_paths=None, selected_path=None, simple=False):
    """parseDifferences(repository, [commit] | [from_commit, to_commit][, selected_path]) =>
         dict(parent_sha1 => [diff.File, ...] (if selected_path is None)
         diff.File                            (if selected_path is not None)"""

    options = []

    if to_commit:
        command = 'diff'
        if from_commit:
            what = [from_commit.sha1 + ".." + to_commit.sha1]
        else:
            what = [GIT_EMPTY_TREE, to_commit.sha1]
    elif not commit.parents:
        # Root commit.

        command = "show"
        what = [commit.sha1]

        options.append("--pretty=format:")
    else:
        assert len(commit.parents) == 1

        command = 'diff'
        what = [commit.parents[0] + '..' + commit.sha1]

    if filter_paths is None and selected_path is None and not simple:
        names = repository.run(command, *(options + ["--name-only"] + what))
        paths = set(filter(None, map(str.strip, names.splitlines())))
    else:
        paths = set()

    if not simple:
        options.append('--ignore-space-change')

    options.extend(what)

    if filter_paths is not None:
        options.append('--')
        options.extend(filter_paths)
    elif selected_path is not None:
        options.append('--')
        options.append(selected_path)

    stdout = repository.run(command, '--full-index', '--unified=1', '--patience', *options)
    selected_file = None

    re_chunk = re.compile('^@@ -(\\d+)(?:,\\d+)? \\+(\\d+)(?:,\\d+)? @@')
    re_binary = re.compile('^Binary files (?:a/(.+)|/dev/null) and (?:b/(.+)|/dev/null) differ')
    re_diff = re.compile("^diff --git ([\"']?)a/(.*)\\1 ([\"']?)b/(.*)\\3$")
    re_old_path = re.compile("--- ([\"']?)a/(.*)\\1\\s*$")
    re_new_path = re.compile("\\+\\+\\+ ([\"']?)b/(.*)\\1\\s*$")

    def isplitlines(text):
        start = 0
        length = len(text)

        while start < length:
            try:
                end = text.index('\n', start)
                yield text[start:end]
                start = end + 1
            except ValueError:
                yield text[start:]
                break

    lines = isplitlines(stdout)

    included = set()
    files = []
    files_by_path = {}

    def addFile(new_file):
        assert new_file.path not in files_by_path, "duplicate path: %s" % new_file.path
        files.append(new_file)
        files_by_path[new_file.path] = new_file
        included.add(new_file.path)

    old_mode = None
    new_mode = None

    try:
        line = lines.next()

        names = None

        while True:
            old_mode = None
            new_mode = None

            # Scan to the 'index <sha1>..<sha1>' line that marks the beginning
            # of the differences in one file.
            while not line.startswith("index "):
                match = re_diff.match(line)
                if match:
                    if old_mode is not None and new_mode is not None:
                        addFile(diff.File(None, names[0], None, None, repository, old_mode=old_mode, new_mode=new_mode, chunks=[]))
                    old_name = match.group(2)
                    if match.group(1):
                        old_name = demunge(old_name)
                    new_name = match.group(4)
                    if match.group(3):
                        new_name = demunge(new_name)
                    names = (old_name, new_name)
                elif line.startswith("old mode "):
                    old_mode = line[9:]
                elif line.startswith("new mode "):
                    new_mode = line[9:]
                elif line.startswith("new file mode "):
                    new_mode = line[14:]
                elif line.startswith("deleted file mode "):
                    old_mode = line[18:]

                line = lines.next()

            is_submodule = False

            try:
                sha1range, mode = line[6:].split(' ', 2)
                if mode == "160000":
                    is_submodule = True
                    old_mode = new_mode = mode
                old_sha1, new_sha1 = sha1range.split('..')
            except:
                old_sha1, new_sha1 = line[6:].split(' ', 1)[0].split("..")

            try: line = lines.next()
            except:
                if old_mode is not None or new_mode is not None:
                    assert names[0] == names[1]

                    addFile(diff.File(None, names[0], old_sha1, new_sha1, repository,
                                      old_mode=old_mode, new_mode=new_mode,
                                      chunks=[diff.Chunk(0, 0, 0, 0)]))

                    old_mode = new_mode = None

            if re_diff.match(line):
                new_file = diff.File(None, names[0] or names[1], old_sha1, new_sha1, repository, old_mode=old_mode, new_mode=new_mode)

                if '0' * 40 == old_sha1 or '0' * 40 == new_sha1:
                    new_file.chunks = [diff.Chunk(0, 0, 0, 0)]
                else:
                    new_file.loadOldLines()
                    new_file.loadNewLines()
                    new_file.chunks = []

                    detectWhiteSpaceChanges(new_file,
                                            new_file.oldLines(False), 1, new_file.oldCount() + 1, True,
                                            new_file.newLines(False), 1, new_file.newCount() + 1, True)


                addFile(new_file)

                old_mode = new_mode = False

                continue

            binary = re_binary.match(line)
            if binary:
                path = (binary.group(1) or binary.group(2)).strip()

                if path in files_by_path:
                    new_file = files_by_path[path]
                    if old_sha1 != '0' * 40:
                        assert new_file.old_sha1 == '0' * 40
                        new_file.old_sha1 = old_sha1
                        new_file.old_mode = old_mode
                    if new_sha1 != '0' * 40:
                        assert new_file.new_sha1 == '0' * 40
                        new_file.new_sha1 = new_sha1
                        new_file.new_mode = new_mode
                    new_file.chunks = [diff.Chunk(0, 0, 0, 0)]
                else:
                    new_file = diff.File(None, path, old_sha1, new_sha1, repository, old_mode=old_mode, new_mode=new_mode)
                    new_file.chunks = [diff.Chunk(0, 0, 0, 0)]
                    addFile(new_file)

                continue

            match = re_old_path.match(line)
            if match:
                old_path = match.group(2)
                if match.group(1):
                    old_path = demunge(old_path)
            else:
                old_path = None

            line = lines.next()

            match = re_new_path.match(line)
            if match:
                new_path = match.group(2)
                if match.group(1):
                    new_path = demunge(new_path)
            else:
                new_path = None

            assert (old_path is None) == ('0' * 40 == old_sha1)
            assert (new_path is None) == ('0' * 40 == new_sha1)

            if old_path:
                path = old_path
            else:
                path = new_path

            if is_submodule:
                line = lines.next()
                match = re_chunk.match(line)
                assert match, repr(line)
                assert match.group(1) == match.group(2) == "1", repr(match.groups())

                line = lines.next()
                assert line == "-Subproject commit %s" % old_sha1, repr(line)

                line = lines.next()
                assert line == "+Subproject commit %s" % new_sha1, repr(line)

                new_file = diff.File(None, path, old_sha1, new_sha1, repository,
                                     old_mode=old_mode, new_mode=new_mode,
                                     chunks=[diff.Chunk(1, 1, 1, 1, analysis="0=0:r18-58=18-58")])

                if path not in files_by_path: addFile(new_file)

                old_mode = new_mode = None

                continue

            try:
                line = lines.next()

                delete_offset = 1
                delete_count = 0
                deleted_lines = []
                insert_offset = 1
                insert_count = 0
                inserted_lines = []

                if old_path and new_path and not simple:
                    old_lines = splitlines(repository.fetch(old_sha1).data)
                    new_lines = splitlines(repository.fetch(new_sha1).data)
                else:
                    old_lines = None
                    new_lines = None

                if path in files_by_path:
                    new_file = files_by_path[path]
                    if old_sha1 != '0' * 40:
                        assert new_file.old_sha1 == '0' * 40
                        new_file.old_sha1 = old_sha1
                        new_file.old_mode = old_mode
                    if new_sha1 != '0' * 40:
                        assert new_file.new_sha1 == '0' * 40
                        new_file.new_sha1 = new_sha1
                        new_file.new_mode = new_mode
                    new_file.chunks = []
                else:
                    new_file = diff.File(None, path, old_sha1, new_sha1, repository, old_mode=old_mode, new_mode=new_mode, chunks=[])

                old_mode = new_mode = None

                if selected_path is not None and selected_path == path:
                    selected_file = new_file

                if path not in files_by_path: addFile(new_file)

                previous_delete_offset = 1
                previous_insert_offset = 1

                while True:
                    match = re_chunk.match(line)

                    if not match: break

                    groups = match.groups()

                    delete_offset = int(groups[0])
                    deleted_lines = []

                    insert_offset = int(groups[1])
                    inserted_lines = []

                    while True:
                        line = lines.next()

                        if line == "\\ No newline at end of file": continue
                        if line[0] not in (' ', '-', '+'): break

                        if line[0] != ' ' and previous_delete_offset is not None and old_lines and new_lines and not simple:
                            detectWhiteSpaceChanges(files[-1], old_lines, previous_delete_offset, delete_offset, True, new_lines, previous_insert_offset, insert_offset, True)
                            previous_delete_offset = None

                        if line[0] == ' ' and previous_delete_offset is None:
                            previous_delete_offset = delete_offset
                            previous_insert_offset = insert_offset

                        type = line[0]

                        if type == '-':
                            delete_offset += 1
                            deleted_lines.append(line[1:])
                        elif type == '+':
                            insert_offset += 1
                            inserted_lines.append(line[1:])
                        else:
                            if deleted_lines or inserted_lines:
                                chunks = createChunks(delete_offset - len(deleted_lines),
                                                      deleted_lines,
                                                      insert_offset - len(inserted_lines),
                                                      inserted_lines)
                                files[-1].chunks.extend(chunks)
                                deleted_lines = []
                                inserted_lines = []

                            delete_offset += 1
                            insert_offset += 1

                    if deleted_lines or inserted_lines:
                        chunks = createChunks(delete_offset - len(deleted_lines),
                                              deleted_lines,
                                              insert_offset - len(inserted_lines),
                                              inserted_lines)
                        files[-1].chunks.extend(chunks)
                        deleted_lines = []
                        inserted_lines = []

                if previous_delete_offset is not None and old_lines and new_lines and not simple:
                    detectWhiteSpaceChanges(files[-1], old_lines, previous_delete_offset, len(old_lines) + 1, True, new_lines, previous_insert_offset, len(new_lines) + 1, True)
                    previous_delete_offset = None
            except StopIteration:
                if deleted_lines or inserted_lines:
                    chunks = createChunks(delete_offset - len(deleted_lines),
                                          deleted_lines,
                                          insert_offset - len(inserted_lines),
                                          inserted_lines)
                    files[-1].chunks.extend(chunks)
                    deleted_lines = []
                    inserted_lines = []

                if previous_delete_offset is not None and old_lines and new_lines and not simple:
                    detectWhiteSpaceChanges(files[-1], old_lines, previous_delete_offset, len(old_lines) + 1, True, new_lines, previous_insert_offset, len(new_lines) + 1, True)

                raise
    except StopIteration:
        if old_mode is not None and new_mode is not None:
            assert names[0] == names[1]

            addFile(diff.File(None, names[0], None, None, repository, old_mode=old_mode, new_mode=new_mode, chunks=[]))

    for path in (paths - included):
        lines = isplitlines(repository.run(command, '--full-index', '--unified=1', *(what + ['--', path])))

        try:
            line = lines.next()

            while not line.startswith("index "): line = lines.next()

            try:
                sha1range, mode = line[6:].split(' ')
                if mode == "160000":
                    continue
                old_sha1, new_sha1 = sha1range.split("..")
            except:
                old_sha1, new_sha1 = line[6:].split(' ', 1)[0].split("..")

            if old_sha1 == '0' * 40 or new_sha1 == '0' * 40:
                # Added or removed empty file.
                continue

            addFile(diff.File(None, path, old_sha1, new_sha1, repository, chunks=[]))

            old_data = repository.fetch(old_sha1).data
            old_lines = splitlines(old_data)
            new_data = repository.fetch(new_sha1).data
            new_lines = splitlines(new_data)

            assert len(old_lines) == len(new_lines), "%s:%d != %s:%d" % (old_sha1, len(old_lines), new_sha1, len(new_lines))

            def endsWithLinebreak(data): return data and data[-1] in "\n\r"

            detectWhiteSpaceChanges(files[-1], old_lines, 1, len(old_lines) + 1, endsWithLinebreak(old_data), new_lines, 1, len(new_lines) + 1, endsWithLinebreak(new_data))
        except StopIteration:
            pass

    if not simple:
        for file in files:
            mergeChunks(file)

    if to_commit:
        if selected_path is not None:
            return selected_file
        elif from_commit:
            return { from_commit.sha1: files }
        else:
            return { None: files }
    elif not commit.parents:
        return { None: files }
    else:
        return { commit.parents[0]: files }
