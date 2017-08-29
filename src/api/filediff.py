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

import api

class FilediffError(api.APIError):
    pass

class FilediffParserError(api.APIError):
    pass

class FilediffDelayed(api.ResultDelayedError):
    pass

class Filediff(api.APIObject):
    """Representation of the source code for a file in a changeset

       A filediff has a list of macro chunks, where each macro chunk represents
       a partition of a file."""

    def __hash__(self):
        return hash(("filediff", self.filechange))
    def __eq__(self, other):
        return self.filechange == other.filechange

    @property
    def filechange(self):
        return self._impl.filechange

    @property
    def old_count(self):
        return self._impl.new_count

    @property
    def new_count(self):
        return self._impl.new_count

    def getMacroChunks(self, context_lines, comments=None, ignore_chunks=False):
        assert isinstance(context_lines, int)
        if comments is not None:
            comments = list(comments)
            assert all(isinstance(comment, api.comment.Comment)
                       for comment in comments)
        assert isinstance(ignore_chunks, bool)
        return self._impl.getMacroChunks(
            self.critic, context_lines, comments, ignore_chunks)

class MacroChunk(object):
    """Representation of a partition of a file

       A macro chunk contains all lines in the range from the first to the last.
       In other words, if a line is between the first and last line of this
       macro chunk, it will be included in this macro chunk.

       A macro chunk also contains old and new offsets and counts, which
       describe where in the file the lines are from, as well as how many are on
       each side. The two sides represents the old and new version of the file,
       where the old version is what the file looked like just before the first
       (earliest) commit of the changeset, and the new version is what the file
       looked like just after the last (latest) commit of the changeset."""

    def __init__(self, impl_macro_chunk):
        self.__impl = impl_macro_chunk

    @property
    def chunks(self):
        return self.__impl.legacy_macro_chunk.chunks

    @property
    def old_offset(self):
        return self.__impl.legacy_macro_chunk.old_offset

    @property
    def new_offset(self):
        return self.__impl.legacy_macro_chunk.new_offset

    @property
    def old_count(self):
        return self.__impl.legacy_macro_chunk.old_count

    @property
    def new_count(self):
        return self.__impl.legacy_macro_chunk.new_count

    @property
    def lines(self):
        return self.__impl.getLines()

class Line(object):
    """Representation of a line of a file

       A line represents a change from the old version of a file, to the new
       version of a file.

       A line has a type, which is one of the following:
         CONTEXT
         DELETED
         MODIFIED
         REPLACED
         INSERTED
         WHITESPACE
         CONFLICT

       The type of the line describes how the line changed.
       """

    def __init__(self, impl_line):
        self.__impl = impl_line

    @property
    def type(self):
        return self.__impl.legacy_line.type

    @property
    def old_offset(self):
        return self.__impl.legacy_line.old_offset

    @property
    def new_offset(self):
        return self.__impl.legacy_line.new_offset

    @property
    def content(self):
        return self.__impl.getContent()

    @property
    def is_whitespace(self):
        return self.__impl.is_whitespace

    @property
    def analysis(self):
        return self.__impl.analysis

    @property
    def type_string(self):
        return self.__impl.type_string()

class Part(object):
    """Representation of a part of a line of code

       A part has a type, which describes what kind of content it contains.
       It can also have a state, meaning the part is either something that was
       removed (in the old version of a file), or added (in the new version of
       a file).

       A part also has some content, which is typically a word (ex. for, in, if)
       or an operator (ex. =, !=, [, ])."""

    def __init__(self, impl_part):
        self.__impl = impl_part

    @property
    def type(self):
        return self.__impl.type

    @property
    def content(self):
        return self.__impl.content

    @property
    def state(self):
        return self.__impl.state

def fetch(critic, filechange):
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(filechange, api.filechange.FileChange), filechange

    return api.impl.filediff.fetch(critic, filechange)

def fetchAll(critic, changeset):
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(changeset, api.changeset.Changeset)
    assert comments is None or isinstance(comments, list)
    assert isinstance(context_lines, int)

    return api.impl.filediff.fetchAll(critic, changeset)
