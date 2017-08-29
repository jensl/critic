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
import diff.context

import json

class Filediff(apiobject.APIObject):
    wrapper_class = api.filediff.Filediff

    def __init__(self, filechange):
        self.filechange = filechange
        self.old_count = None
        self.new_count = None

        self.__chunks = None
        self.__macro_chunks = None
        self.__repository = filechange.changeset.repository

        diff_file = self.__getLegacyFile(filechange.critic)

        self.__highlight_delayed = not diff_file.ensureHighlight("json")

    @staticmethod
    def cache_key(filechange):
        return (filechange.changeset.id, filechange.file.id)

    def __getChunks(self, critic):
        if self.__chunks is None:
            cached_objects = Filediff.allCached(critic)
            assert Filediff.cache_key(self.filechange) in cached_objects

            cached_by_changeset = {}
            for (changeset_id, file_id), filediff in cached_objects.items():
                if filediff._impl.__chunks is None:
                    filediff._impl.__chunks = []
                    cached_by_changeset.setdefault(changeset_id, []) \
                        .append(file_id)

            cursor = critic.getDatabaseCursor()
            for changeset_id, file_ids in cached_by_changeset.items():
                cursor.execute(
                    """SELECT file,
                              deleteOffset, deleteCount,
                              insertOffset, insertCount,
                              analysis, whitespace
                         FROM chunks
                        WHERE changeset=%s
                          AND file=ANY (%s)
                     ORDER BY file, deleteOffset, insertOffset""",
                    (changeset_id, file_ids))

                for (file_id,
                     delete_offset, delete_count,
                     insert_offset, insert_count,
                     analysis, is_whitespace) in cursor:
                    cached_objects[(changeset_id, file_id)]._impl.__chunks \
                        .append(diff.Chunk(delete_offset, delete_count,
                                           insert_offset, insert_count,
                                           analysis=analysis,
                                           is_whitespace=is_whitespace))

        return self.__chunks

    def __getLegacyFile(self, critic):
        return diff.File(
            self.filechange.file.id, self.filechange.file.path,
            self.filechange.old_sha1, self.filechange.new_sha1,
            self.__repository._impl.getInternal(critic),
            old_mode=self.filechange.old_mode,
            new_mode=self.filechange.new_mode)

    def getMacroChunks(self, critic, context_lines, comments, ignore_chunks):
        def create_line_filter(location, context_lines):
            def line_filter(line):
                first_context_line = location.first_line - context_lines
                last_context_line = location.last_line + context_lines

                if location.side == "old":
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
            if self.__highlight_delayed:
                raise api.filediff.FilediffDelayed()

            diff_file = self.__getLegacyFile(critic)

            diff_file.loadOldLines(True, highlight_mode="json")
            diff_file.loadNewLines(True, highlight_mode="json")

            self.old_count = diff_file.oldCount()
            self.new_count = diff_file.newCount()

            diff_chunks = self.__getChunks(critic)

            if comments is not None:
                translated_comments = []
                skinny_comment_chains = []

                for comment in comments:
                    if not isinstance(
                            comment.location, api.comment.FileVersionLocation):
                        continue
                    if comment.location.file != self.filechange.file:
                        continue

                    location = comment.location.translateTo(
                        self.filechange.changeset)

                    if not location:
                        continue

                    translated_comments.append((comment, location))
                    skinny_comment_chains.append((
                        SkinnyCommentChain(critic, location),
                        location.side == "old"))
            else:
                translated_comments = None
                skinny_comment_chains = None

            if ignore_chunks and translated_comments:
                line_filter = create_line_filter(
                    translated_comments[0][1], context_lines)
            else:
                line_filter = None

            diff_context_lines = diff.context.ContextLines(
                diff_file, diff_chunks, skinny_comment_chains)

            legacy_macro_chunks = diff_context_lines.getMacroChunks(
                context_lines, skip_interline_diff=True,
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
        line.__content = None
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

    def getContent(self):
        if self.__content is None:
            old_value = self.legacy_line.old_value
            new_value = self.legacy_line.new_value

            old_content = parts_from_html(self.legacy_line.old_value)

            if self.legacy_line.type == Line.CONTEXT:
                content = old_content
            else:
                new_content = parts_from_html(self.legacy_line.new_value)

                if self.legacy_line.analysis:
                    content = perform_detailed_operations(
                        self.legacy_line.analysis, old_content, new_content)
                else:
                    content = perform_basic_operations(
                        self.legacy_line.type, old_content, new_content)

            self.__content = [api.filediff.Part(part)
                              for part in content]
        return self.__content

class Part(object):
    def __init__(self, part_type, content, state=None):
        self.type = part_type
        self.content = content
        self.state = state

    def copy(self):
        return Part(self.type, self.content, self.state)

    def with_state(self, state):
        self.state = state
        return self

class SkinnyCommentChain(object):
    def __init__(self, critic, location):
        filechange = api.filechange.fetch(
            critic, location.changeset, location.file)

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

def fetch(critic, filechange):
    cache_key = Filediff.cache_key(filechange)
    try:
        return Filediff.get_cached(critic, cache_key)
    except KeyError:
        pass
    filediff = Filediff(filechange).wrap(critic)
    Filediff.add_cached(critic, cache_key, filediff)
    return filediff

def fetchAll(critic, changeset):
    return [
        fetch(critic, filechange)
        for filechange
        in changeset.files
    ]

def parts_from_html(content):
    if content is None:
        return None

    return (Part(part_json[0], part_json[1].encode("utf-8"))
            for part_json in json.loads(content))

class Parts(object):
    def __init__(self, parts):
        self.parts = list(parts)
        self.offset = 0

    def extract(self, length):
        self.offset += length
        while self.parts and len(self.parts[0].content) <= length:
            part = self.parts.pop(0)
            length -= len(part.content)
            yield part
        if length:
            tail_part = self.parts[0]
            head_part = tail_part.copy()
            head_part.content = head_part.content[:length]
            tail_part.content = tail_part.content[length:]
            yield head_part

    def skip(self, length):
        for part in self.extract(length):
            pass

def perform_detailed_operations(operations, old_content, new_content):
    processed_content = []

    old_parts = Parts(old_content)
    new_parts = Parts(new_content)

    for operation in operations:
        if operation[0] == "r":
            old_range, _, new_range = operation[1:].partition("=")
        elif operation[0] == "d":
            old_range = operation[1:]
            new_range = None
        else:
            old_range = None
            new_range = operation[1:]

        if old_range:
            old_begin, old_end = map(int, old_range.split("-"))

        if new_range:
            new_begin, new_end = map(int, new_range.split("-"))

        if old_range:
            context_length = old_begin - old_parts.offset
            if context_length:
                processed_content.extend(old_parts.extract(context_length))
                new_parts.skip(context_length)

            deleted_length = old_end - old_begin
            processed_content.extend(
                part.with_state("d")
                for part in old_parts.extract(deleted_length))

        if new_range:
            if not old_range:
                context_length = new_begin - new_parts.offset
                if context_length:
                    processed_content.extend(old_parts.extract(context_length))
                    new_parts.skip(context_length)

            inserted_length = new_end - new_begin
            processed_content.extend(
                part.with_state("i")
                for part in new_parts.extract(inserted_length))

    processed_content.extend(old_parts.parts)

    return processed_content

def perform_basic_operations(line_type, old_content, new_content):
    if old_content is not None and new_content is not None:
        return ([part.with_state("d") for part in old_content or []] +
                [part.with_state("i") for part in new_content or []])
    elif old_content is not None:
        return old_content
    return new_content
