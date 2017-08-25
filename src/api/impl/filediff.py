# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

from __future__ import absolute_import

import api
import api.impl
from api.impl import apiobject
import diff

import sys

class Filediff(apiobject.APIObject):
    wrapper_class = api.filediff.Filediff

    def __init__(self, critic, repository, filechange, context_lines,
                 comments, ignore_chunks):
        self.filechange = filechange
        self.old_count = None
        self.new_count = None

        self.__macro_chunks = None
        self.__repository = repository
        self.__comments = comments
        self.__context_lines = context_lines
        self.__ignore_chunks = ignore_chunks

    def getMacroChunks(self, critic):
        def diff_file_from_filechange(critic, repository, fc):
            diff_file = diff.File(
                fc.id, fc.path, fc.old_sha1, fc.new_sha1,
                repository._impl.getInternal(critic), old_mode=fc.old_mode,
                new_mode=fc.new_mode)
            diff_file.loadOldLines(True, request_highlight=True)
            diff_file.loadNewLines(True, request_highlight=True)
            return diff_file

        def diff_chunks_from_filechange(fc):
            return [
                diff.Chunk(chunk.deleteoffset, chunk.deletecount,
                           chunk.insertoffset, chunk.insertcount,
                           is_whitespace=chunk.is_whitespace,
                           analysis=chunk.analysis)
                for chunk
                in fc.chunks
            ]

        def create_line_filter(comment, context_lines):
            def line_filter(line):
                first_context_line = comment.location.first_line - context_lines
                last_context_line = comment.location.last_line + context_lines

                if comment.location.side == "old":
                    line_number = line.old_offset
                    if line_number == first_context_line and line.type == diff.Line.INSERTED:
                        return False

                else:
                    line_number = line.new_offset
                    if line_number == first_context_line and line.type == diff.Line.DELETED:
                        return False

                return first_context_line <= line_number <= last_context_line
            return line_filter

        if self.__macro_chunks is None:
            self.diff_file = diff_file_from_filechange(
                critic, self.__repository, self.filechange)

            diff_chunks = diff_chunks_from_filechange(self.filechange)

            if self.__comments is not None:
                comment_chains = [
                    (SkinnyCommentChain(critic, comment),
                     comment.location.side == "old")
                    for comment
                    in self.__comments
                    if isinstance(comment.location, api.comment.FileVersionLocation)
                ]
            else:
                comment_chains = None

            if self.__ignore_chunks and isinstance(
                    self.__comments[0].location, api.comment.FileVersionLocation):
                line_filter = create_line_filter(self.__comments[0], self.__context_lines)
            else:
                line_filter = None

            diff_context_lines = diff.context.ContextLines(
                self.diff_file, diff_chunks, comment_chains)

            legacy_macro_chunks = diff_context_lines.getMacroChunks(
                self.__context_lines, skip_interline_diff=True,
                lineFilter=line_filter)

            self.__macro_chunks = [
                api.filediff.MacroChunk(MacroChunk(critic, legacy_macro_chunk))
                for legacy_macro_chunk
                in legacy_macro_chunks
            ]
        return self.__macro_chunks

class MacroChunk(object):
    def __init__(self, critic, legacy_macro_chunk):
        self.legacy_macro_chunk = legacy_macro_chunk
        self.old_offset = legacy_macro_chunk.old_offset
        self.new_offset = legacy_macro_chunk.new_offset
        self.old_count = legacy_macro_chunk.old_count
        self.new_count = legacy_macro_chunk.new_count
        self.__lines = None

    def getLines(self):
        if self.__lines is None:
            self.__lines = [
                api.filediff.Line(Line.from_legacy_line(line))
                for line
                in self.legacy_macro_chunk.lines
            ]
        return self.__lines

class Line(object):
    CONTEXT    = 1
    DELETED    = 2
    MODIFIED   = 3
    REPLACED   = 4
    INSERTED   = 5
    WHITESPACE = 6
    CONFLICT   = 7

    @classmethod
    def from_legacy_line(self, legacy_line):
        line = Line()
        line.legacy_line = legacy_line
        line.__old_content = None
        line.__new_content = None
        line.is_whitespace = legacy_line.is_whitespace
        line.analysis = legacy_line.analysis
        return line

    @classmethod
    def from_changed_line(self, original_line, old_content_replacement,
                          new_content_replacement):
        line = Line()
        line.legacy_line = original_line.legacy_line
        line.__old_content = old_content_replacement
        line.__new_content = new_content_replacement
        line.is_whitespace = original_line.is_whitespace
        return line

    def type_string(self):
        if self.legacy_line.type == Line.CONTEXT: return "CONTEXT"
        elif self.legacy_line.type == Line.DELETED: return "DELETED"
        elif self.legacy_line.type == Line.MODIFIED: return "MODIFIED"
        elif self.legacy_line.type == Line.REPLACED: return "REPLACED"
        elif self.legacy_line.type == Line.INSERTED: return "INSERTED"
        elif self.legacy_line.type == Line.WHITESPACE: return "WHITESPACE"
        elif self.legacy_line.type == Line.CONFLICT: return "CONFLICT"

    def getOldContent(self):
        if self.__old_content is None and self.legacy_line.old_value is not None:
            old_content_intermediate = parts_from_html(self.legacy_line.old_value)

            if self.legacy_line.analysis:
                old_content = perform_operations(
                    self.legacy_line.analysis, old_content_intermediate, True)
            else:
                old_content = old_content_intermediate
            self.__old_content = [api.filediff.Part(part)
                                  for part in old_content]
        return self.__old_content

    def getNewContent(self):
        if self.__new_content is None and self.legacy_line.new_value is not None:
            new_content_intermediate = parts_from_html(self.legacy_line.new_value)

            if self.legacy_line.analysis:
                new_content = perform_operations(
                    self.legacy_line.analysis, new_content_intermediate, False)
            else:
                new_content = new_content_intermediate
            self.__new_content = [api.filediff.Part(part)
                                  for part in new_content]
        return self.__new_content

class Part(object):
    def __init__(self, part_type, content, state=None):
        self.type = part_type
        self.content = content.replace("&lt;", "<") \
                              .replace("&gt;", ">") \
                              .replace("&amp;", "&")
        self.state = state

class SkinnyCommentChain(object):
    def __init__(self, critic, comment):
        assert isinstance(comment.location, api.comment.FileVersionLocation)

        location = comment.location

        filechange = api.filechange.fetch(
            critic, location.changeset, location.file.id)

        if location.side == "old":
            key = filechange.old_sha1
        else:
            key = filechange.new_sha1

        self.lines_by_sha1 = {}
        self.lines_by_sha1[key] = (
            location.first_line,
            location.last_line - location.first_line + 1
        )

        self.comments = True

def fetch(critic, repository, filechange, context_lines, comments,
          ignore_chunks):
    return Filediff(critic, repository, filechange, context_lines, comments,
                    ignore_chunks) \
        .wrap(critic)

def fetchAll(critic, repository, changeset, context_lines, comments):
    filechanges = api.filechange.fetchAll(critic, changeset)
    return [
        fetch(critic, repository, filechange, context_lines, comments,
              ignore_chunks=False)
        for filechange
        in filechanges
    ]

def parts_from_html(content):
    if content is None:
        return None

    parts = content.split("</b>")
    if not parts:
        return [Part("nf", content)]
    elements = []
    for part in parts:
        if not part:
            continue
        leading_text, _, content = part.partition("<b")
        if content == "":
            elements.append(Part("ws", part))
        else:
            if leading_text:
                elements.append(Part("ws", leading_text))
            part_type = content.split("='")[1].split("'")[0]
            tag, _, part_content = content.partition(">")
            elements.append(Part(part_type, part_content))
    return elements

def op_and_part_collides(op_start, op_end, part_start, part_end):
    return op_start < part_end and part_start < op_end

def collision_type(op_start, op_end, part_start, part_end):
    if part_start == op_start and part_end == op_end:
        return "OP_IS_PART"
    elif part_start <= op_start and part_end >= op_end:
        return "OP_IN_PART"
    elif part_start >= op_start and part_end <= op_end:
        return "PART_IN_OP"
    elif part_start > op_start and part_end > op_end:
        return "PART_AFTER_OP"
    elif part_start < op_start and part_end < op_end:
        return "PART_BEFORE_OP"

def get_op_start_end(operation, operands, old):
    if old and operation[0] in ("d", "r"):
        operand_index = 0
    elif not old and operation[0] == "i":
        operand_index = 0
    elif not old and operation[0] == "r":
        operand_index = 1
    else:
        raise api.filediff.FilediffParserError("unknown operation: " + operation)

    op_start, op_end = operands[operand_index].split("-")

    return (int(op_start), int(op_end))

def apply_op_is_part(part, state):
    part.state = state
    return part

def apply_op_in_part(part, state, part_start, part_end, op_start, op_end):
    parts = []

    before_content = part.content[0:op_start-part_start]
    if before_content:
        parts.append(Part(part.type, before_content))

    during_content = part.content[op_start-part_start:op_end-part_start]
    parts.append(Part(part.type, during_content, state))

    after_content = part.content[op_end-part_start:part_end-part_start]
    if after_content:
        parts.append(Part(part.type, after_content))

    return parts

def apply_op_overlapping_part(part, state, part_start, part_end, op_start, op_end, part_after_op):
    if part_after_op:
        before_state = state
        after_state = None
        divide_point = op_end-part_start
    else:
        before_state = None
        after_state = state
        divide_point = op_start-part_start

    before_part = Part(part.type, part.content[:divide_point], before_state)
    after_part = Part(part.type, part.content[divide_point:], after_state)

    return [before_part, after_part]

def perform_operations(operations, content, old):
    assert isinstance(operations, list)
    assert isinstance(content, list)
    assert isinstance(old, bool)

    if old:
        state = "d"
    else:
        state = "i"

    processed_content = []
    part_index = 0
    part_start = 0
    op_index = 0

    while part_index < len(content) and \
          op_index < len(operations):
        operation = operations[op_index]
        operands = operation[1:].split("=")
        part = content[part_index]
        part_end = part_start + len(part.content)

        if (operation[0] == "d" and not old) or \
           (operation[0] == "i" and old):
            op_index += 1
            continue
        elif operation == "ws":
            op_index += 1
            continue
        else:
            op_start, op_end = get_op_start_end(operation, operands, old)

        if op_and_part_collides(op_start, op_end, part_start, part_end):
            start_end = (op_start, op_end, part_start, part_end)
            collision = collision_type(*start_end)

            if collision == "OP_IS_PART":
                processed_content.append(apply_op_is_part(
                    part, state))

            elif collision == "OP_IN_PART":
                processed_content.extend(apply_op_in_part(
                    part, state, *start_end))

                op_index += 1

            elif collision == "PART_IN_OP":
                processed_content.append(Part(part.type, part.content, state))

            elif collision == "PART_AFTER_OP":
                processed_content.extend(apply_op_overlapping_part(
                    part, state, *start_end, part_after_op=True))

                op_index += 1

            elif collision == "PART_BEFORE_OP":
                processed_content.extend(apply_op_overlapping_part(
                    part, state, *start_end, part_after_op=False))

            else:
                raise api.filediff.FilediffParserError(
                    "invalid collision type: " + str(collision) +
                    " (" + str(op_start) + ", " + str(op_end) + ", " +
                    str(part_start) + ", " + str(part_end) + ")")

            part_index += 1
            part_start += len(part.content)

        elif op_end <= part_start:
            op_index += 1
        elif part_start <= op_end:
            processed_content.append(part)
            part_start += len(part.content)
            part_index += 1

    if part_index < len(content):
        processed_content.extend(content[part_index:])

    return processed_content
