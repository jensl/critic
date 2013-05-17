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
import diff.html

class ContextLines:
    def __init__(self, file, chunks, chains=None, merge=False, conflicts=False):
        self.file = file
        self.chunks = chunks
        self.chains = chains
        self.merge = merge
        self.conflicts = conflicts

    def getMacroChunks(self, context_lines=3, minimum_gap=3, highlight=True, lineFilter=None):
        old_lines = self.file.oldLines(highlight)
        new_lines = self.file.newLines(highlight)

        lines = []

        def addLine(line):
            if not lineFilter or lineFilter(line): lines.append(line)

        for chunk in self.chunks:
            old_offset = chunk.delete_offset
            new_offset = chunk.insert_offset

            if chunk.analysis:
                mappings = chunk.analysis.split(';')

                for mapping in mappings:
                    if ':' in mapping:
                        mapped_lines, ops = mapping.split(':')
                    else:
                        mapped_lines = mapping
                        ops = None

                    old_line, new_line = mapped_lines.split('=')
                    old_line = chunk.delete_offset + int(old_line)
                    new_line = chunk.insert_offset + int(new_line)

                    while old_offset < old_line and new_offset < new_line:
                        if old_lines[old_offset - 1] == new_lines[new_offset - 1]:
                            line_type = diff.Line.CONTEXT
                        else:
                            line_type = diff.Line.REPLACED

                        line = diff.Line(line_type,
                                         old_offset, old_lines[old_offset - 1],
                                         new_offset, new_lines[new_offset - 1],
                                         is_whitespace=chunk.is_whitespace)

                        if self.conflicts and line_type == diff.Line.REPLACED and line.isConflictMarker():
                            addLine(diff.Line(diff.Line.DELETED,
                                              old_offset, old_lines[old_offset - 1],
                                              new_offset, None))
                        else:
                            addLine(line)
                            new_offset += 1

                        old_offset += 1

                    while old_offset < old_line:
                        addLine(diff.Line(diff.Line.DELETED,
                                          old_offset, old_lines[old_offset - 1],
                                          new_offset, None))
                        old_offset += 1

                    while new_offset < new_line:
                        addLine(diff.Line(diff.Line.INSERTED,
                                          old_offset, None,
                                          new_offset, new_lines[new_offset - 1]))
                        new_offset += 1

                    try:
                        deleted_line = old_lines[old_offset - 1]
                        inserted_line = new_lines[new_offset - 1]
                    except:
                        raise repr((self.file.path, self.file.old_sha1, self.file.new_sha1, new_offset, len(new_lines)))

                    if deleted_line == inserted_line:
                        line_type = diff.Line.CONTEXT
                        is_whitespace = False
                    else:
                        if ops and ops.startswith("ws"):
                            is_whitespace = True
                            if ops.startswith("ws,"): ops = ops[3:]
                            else: ops = None
                        else:
                            is_whitespace = False

                        line_type = diff.Line.MODIFIED

                        if highlight and ops:
                            if ops == "eol":
                                line_type = diff.Line.REPLACED
                                if highlight:
                                    if not self.file.old_eof_eol: deleted_line += "<i class='eol'>[missing linebreak]</i>"
                                    if not self.file.new_eof_eol: deleted_line += "<i class='eol'>[missing linebreak]</i>"
                            else:
                                deleted_line, inserted_line = diff.html.lineDiffHTML(ops, deleted_line, inserted_line)

                    addLine(diff.Line(line_type,
                                      old_offset, deleted_line,
                                      new_offset, inserted_line,
                                      is_whitespace=chunk.is_whitespace or is_whitespace))

                    old_offset += 1
                    new_offset += 1

            old_line = chunk.delete_offset + chunk.delete_count
            new_line = chunk.insert_offset + chunk.insert_count

            while old_offset < old_line and new_offset < new_line:
                if old_lines[old_offset - 1] == new_lines[new_offset - 1]:
                    line_type = diff.Line.CONTEXT
                else:
                    line_type = diff.Line.REPLACED

                line = diff.Line(line_type,
                                 old_offset, old_lines[old_offset - 1],
                                 new_offset, new_lines[new_offset - 1],
                                 is_whitespace=chunk.is_whitespace)

                if self.conflicts and line_type == diff.Line.REPLACED and line.isConflictMarker():
                    addLine(diff.Line(diff.Line.DELETED,
                                      old_offset, old_lines[old_offset - 1],
                                      new_offset, None))
                else:
                    addLine(line)
                    new_offset += 1

                old_offset += 1

            while old_offset < old_line:
                try:
                    addLine(diff.Line(diff.Line.DELETED,
                                      old_offset, old_lines[old_offset - 1],
                                      new_offset, None))
                except:
                    addLine(diff.Line(diff.Line.DELETED,
                                      old_offset, "",
                                      new_offset, None))

                old_offset += 1

            while new_offset < new_line:
                try:
                    addLine(diff.Line(diff.Line.INSERTED,
                                      old_offset, None,
                                      new_offset, new_lines[new_offset - 1]))
                except:
                    addLine(diff.Line(diff.Line.INSERTED,
                                      old_offset, None,
                                      new_offset, ""))

                new_offset += 1

        old_table = {}
        new_table = {}

        for line in lines:
            if line.old_value is not None:
                old_table[line.old_offset] = line
            if line.new_value is not None:
                new_table[line.new_offset] = line

        def translateInChunk(chunk, old_delta=None, new_delta=None):
            if chunk.analysis:
                mappings = chunk.analysis.split(';')

                previous_old_line = 0
                previous_new_line = 0

                for mapping in mappings:
                    if ':' in mapping:
                        mapped_lines, ops = mapping.split(':')
                    else:
                        mapped_lines = mapping

                    old_line, new_line = mapped_lines.split('=')
                    old_line = int(old_line)
                    new_line = int(new_line)

                    if old_delta is not None:
                        if old_line == old_delta:
                            return new_line
                        elif old_line > old_delta:
                            return previous_new_line
                    else:
                        if new_line == new_delta:
                            return old_line
                        elif new_line > new_delta:
                            return previous_old_line

                    previous_old_line = old_line
                    previous_new_line = new_line

            if old_delta is not None: return min(old_delta, chunk.insert_count)
            else: return min(new_delta, chunk.delete_count)

        def findMatchingOldOffset(offset):
            precedingChunk = None
            for chunk in self.chunks:
                if chunk.insert_offset + chunk.insert_count > offset:
                    if chunk.insert_offset <= offset:
                        delta = translateInChunk(chunk, new_delta=offset - chunk.insert_offset)
                        offset = chunk.delete_offset + delta
                        return offset
                    break
                precedingChunk = chunk
            if precedingChunk:
                offset -= precedingChunk.insert_offset + precedingChunk.insert_count
                offset += precedingChunk.delete_offset + precedingChunk.delete_count
            return offset

        def findMatchingNewOffset(offset):
            precedingChunk = None
            for chunk in self.chunks:
                if chunk.delete_offset + chunk.delete_count > offset:
                    if chunk.delete_offset <= offset:
                        delta = translateInChunk(chunk, old_delta=offset - chunk.delete_offset)
                        offset = chunk.insert_offset + delta
                        return offset
                    break
                precedingChunk = chunk
            if precedingChunk:
                offset -= precedingChunk.delete_offset + precedingChunk.delete_count
                offset += precedingChunk.insert_offset + precedingChunk.insert_count
            return offset

        if self.chains and not self.merge:
            for chain in self.chains:
                if chain.comments:
                    if self.file.new_sha1 in chain.lines_by_sha1:
                        chain_offset, chain_count = chain.lines_by_sha1[self.file.new_sha1]
                        old_offset = findMatchingOldOffset(chain_offset)
                        new_offset = chain_offset
                        first_line = new_table.get(new_offset)
                    else:
                        chain_offset, chain_count = chain.lines_by_sha1[self.file.old_sha1]
                        old_offset = chain_offset
                        new_offset = findMatchingNewOffset(chain_offset)
                        first_line = old_table.get(old_offset)

                    count = chain_count

                    while count:
                        if old_offset not in old_table and new_offset not in new_table:
                            try:
                                line = diff.Line(diff.Line.CONTEXT,
                                                 old_offset, old_lines[old_offset - 1],
                                                 new_offset, new_lines[new_offset - 1])
                            except IndexError:
                                break
                            if not lineFilter or lineFilter(line):
                                if not first_line: first_line = line
                                old_table[old_offset] = line
                                new_table[new_offset] = line

                        if old_offset in old_table: old_offset += 1
                        if new_offset in new_table: new_offset += 1
                        count -= 1

        class queue:
            def __init__(self, iterable):
                self.__list = list(iterable)
                self.__offset = 0

            def __getitem__(self, index): return self.__list[self.__offset + index]
            def __nonzero__(self): return self.__offset < len(self.__list)
            def __len__(self): return len(self.__list) - self.__offset
            def __str__(self): return str(self.__list[self.__offset:])
            def __repr__(self): return repr(self.__list[self.__offset:])

            def pop(self):
                self.__offset += 1
                return self.__list[self.__offset - 1]

        all_lines = queue(sorted([(key, value.new_offset, value) for key, value in old_table.items()] +
                                 [(value.old_offset, key, value) for key, value in new_table.items() if value.type not in (diff.Line.CONTEXT, diff.Line.MODIFIED, diff.Line.REPLACED)]))
        all_chunks = self.chunks[:]
        all_chains = self.chains and self.chains[:] or None

        macro_chunks = []

        def lineOrNone(lines, index):
            try: return lines[index]
            except IndexError: return None

        while all_lines:
            old_offset, new_offset, first_line = all_lines.pop()

            count = min(context_lines, max(old_offset - 1, new_offset - 1))
            old_offset = max(1, old_offset - count)
            new_offset = max(1, new_offset - count)
            lines = []

            while count:
                if old_offset <= len(old_lines) and new_offset <= len(new_lines):
                    addLine(diff.Line(diff.Line.CONTEXT,
                                      old_offset, old_lines[old_offset - 1],
                                      new_offset, new_lines[new_offset - 1]))
                    old_offset += 1
                    new_offset += 1
                elif old_offset <= len(old_lines):
                    old_offset += 1
                else:
                    new_offset += 1
                count -= 1

            lines.append(first_line)
            if first_line.type != diff.Line.INSERTED: old_offset += 1
            if first_line.type != diff.Line.DELETED: new_offset += 1

            while all_lines:
                while all_lines and (old_offset == all_lines[0][0] or new_offset == all_lines[0][1]):
                    line = all_lines.pop()[2]
                    lines.append(line)
                    if line.type != diff.Line.INSERTED: old_offset += 1
                    if line.type != diff.Line.DELETED: new_offset += 1

                if all_lines and all_lines[0][1] - new_offset <= 2 * context_lines + minimum_gap:
                    while old_offset != all_lines[0][0] and new_offset != all_lines[0][1]:
                        line = diff.Line(diff.Line.CONTEXT,
                                         old_offset, lineOrNone(old_lines, old_offset - 1),
                                         new_offset, lineOrNone(new_lines, new_offset - 1))
                        addLine(line)
                        if line.old_value is not None: old_offset += 1
                        if line.new_value is not None: new_offset += 1
                else: break

            count = context_lines

            while count:
                if old_offset <= len(old_lines) and new_offset <= len(new_lines):
                    addLine(diff.Line(diff.Line.CONTEXT,
                                      old_offset, old_lines[old_offset - 1],
                                      new_offset, new_lines[new_offset - 1]))
                    old_offset += 1
                    new_offset += 1
                elif old_offset <= len(old_lines):
                    old_offset += 1
                else:
                    new_offset += 1
                count -= 1

            chunks = []

            while all_chunks and (all_chunks[0].delete_offset < old_offset or all_chunks[0].insert_offset < new_offset):
                chunks.append(all_chunks.pop(0))

            chains = []

            if all_chains:
                index = 0
                while index < len(all_chains):
                    chain = all_chains[index]

                    if self.file.new_sha1 in chain.lines_by_sha1:
                        chain_offset, chain_count = chain.lines_by_sha1[self.file.new_sha1]
                        compare_offset = new_offset
                    else:
                        chain_offset, chain_count = chain.lines_by_sha1[self.file.old_sha1]
                        compare_offset = old_offset

                    if chain_offset < compare_offset:
                        chains.append(chain)
                        del all_chains[index]
                    else:
                        index += 1

            macro_chunks.append(diff.MacroChunk(chunks, lines))

        if not lineFilter:
            return filter(lambda macro_chunk: bool(macro_chunk.chunks), macro_chunks)
        else:
            return macro_chunks
