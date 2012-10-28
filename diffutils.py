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

import re
from difflib import SequenceMatcher
from itertools import izip, repeat

import diff
import diff.html

def expandWithContext(chunks, old_lines, new_lines, context_lines, highlight=True):
    if not chunks: return []

    groups = []
    group = []

    chunks = iter(chunks)

    try:
        previousChunk = chunks.next()
        group.append(previousChunk)

        while True:
            nextChunk = chunks.next()

            distance = nextChunk.delete_offset - (previousChunk.delete_offset + previousChunk.delete_count)
            gap_between = distance - 2 * context_lines

            if gap_between >= 3:
                groups.append(group)
                group = []

            group.append(nextChunk)
            previousChunk = nextChunk
    except StopIteration:
        pass

    groups.append(group)

    macro_chunks = []

    for group in groups:
        delete_offset = max(1, group[0].delete_offset - context_lines)
        insert_offset = max(1, group[0].insert_offset - context_lines)

        lines = []

        for chunk in group:
            while delete_offset < chunk.delete_offset:
                lines.append(diff.Line(diff.Line.CONTEXT, delete_offset, old_lines[delete_offset - 1], insert_offset, new_lines[insert_offset - 1]))
                delete_offset += 1
                insert_offset += 1

            if chunk.analysis:
                mappings = chunk.analysis.split(';')

                for mapping in mappings:
                    if ':' in mapping:
                        mapped_lines, ops = mapping.split(':')
                    else:
                        mapped_lines = mapping
                        ops = None

                    delete_line, insert_line = mapped_lines.split('=')
                    delete_line = chunk.delete_offset + int(delete_line)
                    insert_line = chunk.insert_offset + int(insert_line)

                    while delete_offset < delete_line and insert_offset < insert_line:
                        lines.append(diff.Line(diff.Line.MODIFIED, delete_offset, old_lines[delete_offset - 1], insert_offset, new_lines[insert_offset - 1], is_whitespace=chunk.is_whitespace))
                        delete_offset += 1
                        insert_offset += 1

                    while delete_offset < delete_line:
                        lines.append(diff.Line(diff.Line.DELETED, delete_offset, old_lines[delete_offset - 1], insert_offset, None))
                        delete_offset += 1

                    while insert_offset < insert_line:
                        lines.append(diff.Line(diff.Line.INSERTED, delete_offset, None, insert_offset, new_lines[insert_offset - 1]))
                        insert_offset += 1

                    deleted_line = old_lines[delete_offset - 1]
                    inserted_line = new_lines[insert_offset - 1]

                    if highlight and ops: deleted_line, inserted_line = diff.html.lineDiffHTML(ops, deleted_line, inserted_line)

                    lines.append(diff.Line(diff.Line.MODIFIED, delete_offset, deleted_line, insert_offset, inserted_line, is_whitespace=chunk.is_whitespace))

                    delete_offset += 1
                    insert_offset += 1

            deleteStop = chunk.delete_offset + chunk.delete_count
            insertStop = chunk.insert_offset + chunk.insert_count

            while delete_offset < deleteStop and insert_offset < insertStop:
                lines.append(diff.Line(diff.Line.REPLACED, delete_offset, old_lines[delete_offset - 1], insert_offset, new_lines[insert_offset - 1], is_whitespace=chunk.is_whitespace))
                delete_offset += 1
                insert_offset += 1

            while delete_offset < deleteStop:
                lines.append(diff.Line(diff.Line.DELETED, delete_offset, old_lines[delete_offset - 1], insert_offset, None))
                delete_offset += 1

            while insert_offset < insertStop:
                lines.append(diff.Line(diff.Line.INSERTED, delete_offset, None, insert_offset, new_lines[insert_offset - 1]))
                insert_offset += 1

        deleteStop = min(len(old_lines) + 1, delete_offset + context_lines)

        while delete_offset < deleteStop:
            lines.append(diff.Line(diff.Line.CONTEXT, delete_offset, old_lines[delete_offset - 1], insert_offset, new_lines[insert_offset - 1]))
            delete_offset += 1
            insert_offset += 1

        macro_chunks.append(diff.MacroChunk(group, lines))

    return macro_chunks
