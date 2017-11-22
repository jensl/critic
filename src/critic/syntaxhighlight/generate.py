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

import errno
import json
import logging
import msgpack
import os

logger = logging.getLogger("syntaxhighlight.generate")

from . import TokenTypes


def createHighlighter(language):
    from . import cpp

    highlighter = cpp.HighlightCPP.create(language)
    if highlighter:
        return highlighter

    from . import generic

    highlighter = generic.HighlightGeneric.create(language)
    if highlighter:
        return highlighter


class Outputter(object):
    def __init__(self, output_file):
        self.output_file = output_file

    def writeMultiline(self, token_type, content):
        parts = content.split("\n")
        for part in parts[:-1]:
            if part:
                self._writePart(token_type, part)
            self._endLine()
        if parts[-1]:
            self._writePart(token_type, parts[-1])

    def writeSingleline(self, token_type, content):
        assert "\n" not in content
        self._writePart(token_type, content)

    def writePlain(self, content):
        parts = content.split("\n")
        for part in parts[:-1]:
            if part:
                self._writePlain(part)
            self._endLine()
        if parts[-1]:
            self._writePlain(parts[-1])

    def flush(self):
        self._flush()
        if self.output_file:
            self.output_file.close()


class StructuredOutputter(Outputter):
    def __init__(self, output_file):
        super().__init__(output_file)
        self.line = []
        self.previous_type = None

    def _writePart(self, token_type, content):
        if self.previous_type == token_type:
            self.line[-1][0] += content
        else:
            self.line.append([content, token_type])
            self.previous_type = token_type

    def _writePlain(self, content):
        if self.previous_type == TokenTypes.Whitespace:
            self.line[-1][0] += content
        else:
            self.line.append([content])
            self.previous_type = TokenTypes.Whitespace

    def _endLine(self):
        self._emitLine(self.line)
        self.line = []
        self.previous_type = None

    def _flush(self):
        if self.line:
            self._emitLine(self.line)


class JSONOutputter(StructuredOutputter):
    def _emitLine(self, line):
        self.output_file.write(json.dumps(line) + "\n")


class MsgpackOutputter(StructuredOutputter):
    def __init__(self):
        super().__init__(None)
        self.result = []

    def _emitLine(self, line):
        self.result.append(msgpack.packb(line, use_bin_type=True))


class LanguageNotSupported(Exception):
    pass


def generate(source, language):
    highlighter = createHighlighter(language)

    if not highlighter:
        logger.debug("language not supported: %s", language)
        raise LanguageNotSupported()

    outputter = MsgpackOutputter()
    contexts = highlighter(source, outputter)

    return outputter.result, contexts
