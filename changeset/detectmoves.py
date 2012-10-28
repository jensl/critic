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

import difflib
import re
import diff
import diff.analyze

re_ws = re.compile("\\s+")

SMALLEST_INSERT = 5
MAXIMUM_GAP = 10

class Line:
    def __init__(self, string):
        self.string = string
        self.wsnorm = re_ws.sub(" ", string.strip())

    def __str__(self):
        return self.string

    def __eq__(self, other):
        return self.wsnorm == other.wsnorm

    def __ne__(self, other):
        return self.wsnorm == other.wsnorm

    def __hash__(self):
        return hash(self.wsnorm)

def compareChunks(source_file, source_chunk, target_file, target_chunk, extra_target_chunks, context_lines=3):
    source_length = source_file.oldCount()
    target_length = target_file.newCount()

    source_lines = map(Line, source_chunk.deleted_lines)
    target_lines = map(Line, target_chunk.inserted_lines)

    sm = difflib.SequenceMatcher(None, source_lines, target_lines)

    blocks = filter(lambda x: x[2], sm.get_matching_blocks())

    if blocks:
        chunks = []

        i, j, n = blocks.pop(0)

        current = [(i, j, n)]
        matched = n

        pi = i + n
        pj = j + n

        for i, j, n in blocks:
            if i - pi > MAXIMUM_GAP or j - pj > MAXIMUM_GAP:
                chunks.append((matched, current))
                current = [(i, j, n)]
                matched = n
            else:
                current.append((i, j, n))
                matched += n
            pi = i + n
            pj = j + n

        chunks.append((matched, current))
        chunks.sort()

        matched, blocks = chunks[-1]

        if matched < SMALLEST_INSERT:
            return None

        source_begin = max(-(source_chunk.delete_offset - 1), blocks[0][0] - context_lines)
        source_end = min(source_length + 1 - source_chunk.delete_offset, blocks[-1][0] + blocks[-1][2] + context_lines)

        target_begin = max(-(target_chunk.insert_offset - 1), blocks[0][1] - context_lines)
        target_end = min(target_length + 1 - target_chunk.insert_offset, blocks[-1][1] + blocks[-1][2] + context_lines)

        new_chunk = diff.Chunk(source_chunk.delete_offset + source_begin,
                               source_end - source_begin,
                               target_chunk.insert_offset + target_begin,
                               target_end - target_begin)

        new_chunk.source_chunk = source_chunk
        new_chunk.source_begin = source_begin
        new_chunk.source_end = source_end
        new_chunk.source_length = source_length

        if blocks[0][1] >= SMALLEST_INSERT and blocks[0][1] < target_chunk.insert_count:
            extra_before = diff.Chunk(0, 0, target_chunk.insert_offset, blocks[0][1])
        else:
            extra_before = None

        match_end = blocks[-1][1] + blocks[-1][2]
        if target_chunk.insert_count - match_end >= SMALLEST_INSERT:
            extra_after = diff.Chunk(0, 0, target_chunk.insert_offset + match_end, target_chunk.insert_count - match_end)
        else:
            extra_after = None

        new_chunk.deleted_lines = source_file.getOldLines(new_chunk)
        new_chunk.inserted_lines = target_file.getNewLines(new_chunk)

        if matched > len(new_chunk.inserted_lines) * 0.25:
            analysis = diff.analyze.analyzeChunk(new_chunk.deleted_lines, new_chunk.inserted_lines, moved=True)

            if matched > len(new_chunk.inserted_lines) * 0.5 or (analysis and len(analysis.split(';')) >= len(new_chunk.inserted_lines) * 0.5):
                new_chunk.analysis = analysis
                if extra_before: extra_target_chunks.append(extra_before)
                if extra_after: extra_target_chunks.append(extra_after)
                return new_chunk

    return None

def findSourceChunk(db, changeset, source_file_ids, target_file, target_chunk, extra_target_chunks):
    for source_file in changeset.files:
        if source_file_ids and not source_file.id in source_file_ids: continue

        for source_chunk in source_file.chunks:
            # Should't compare chunk to itself, of course.
            if target_file == source_file and target_chunk == source_chunk:
                continue

            # Much fewer deleted lines than inserted lines in the target chunk;
            # unlikely to be a relevant source chunk.
            #if source_chunk.delete_count * 1.5 < target_chunk.insert_count:
            #    continue

            if source_chunk.analysis:
                # If more than half the deleted lines are mapped against
                # inserted lines, most likely edited rather than moved code.
                if source_chunk.delete_count < len(source_chunk.analysis.split(";")) * 2:
                    continue

            source_file.loadOldLines()
            source_chunk.deleted_lines = source_file.getOldLines(source_chunk)

            new_chunk = compareChunks(source_file, source_chunk, target_file, target_chunk, extra_target_chunks)

            if new_chunk:
                return source_file, new_chunk

    return None, None

def detectMoves(db, changeset, source_file_ids=None, target_file_ids=None):
    moves = []

    for target_file in changeset.files:
        if target_file_ids and not target_file.id in target_file_ids: continue

        current_chunks = target_file.chunks

        count = 0
        log = ""

        while current_chunks:
            extra_target_chunks = []
            count += 1

            for target_chunk in current_chunks:
                # White-space only changes; unlikely target of moved code.
                if target_chunk.is_whitespace:
                    continue

                # Too few inserted lines; couldn't possibly be an interesting target
                # of moved code.
                if target_chunk.insert_count < 5:
                    continue

                if target_chunk.analysis:
                    # If more than half the inserted lines are mapped against
                    # deleted lines, most likely edited rather than moved code.
                    if target_chunk.insert_count < len(target_chunk.analysis.split(";")) * 2:
                        continue

                target_file.loadNewLines()
                target_chunk.inserted_lines = target_file.getNewLines(target_chunk)

                source_file, chunk = findSourceChunk(db, changeset, source_file_ids, target_file, target_chunk, extra_target_chunks)

                if source_file and chunk:
                    moves.append((source_file, target_file, chunk))
                    continue

            current_chunks = extra_target_chunks

    if moves:
        def orderChunks(a, b):
            a_source_file, a_target_file, a_chunk = a
            b_source_file, b_target_file, b_chunk = b

            c = cmp(a_target_file.path, b_target_file.path)
            if c != 0: return c
            else: return cmp(a_chunk.insert_offset, b_chunk.insert_offset)

        moves.sort(orderChunks)

        move_changeset = diff.Changeset(None, changeset.parent, changeset.child, 'moves', [])

        for source_file, target_file, chunk in moves:
            move_file = diff.File(0, "",
                                  source_file.old_sha1,
                                  target_file.new_sha1,
                                  source_file.repository,
                                  chunks=[chunk],
                                  move_source_file=source_file,
                                  move_target_file=target_file)

            move_changeset.files.append(move_file)

        return move_changeset
    else:
        return None
