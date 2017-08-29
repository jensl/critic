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

import os
import errno

import syntaxhighlight
import gitutils
import textutils
import htmlutils
import diff.parse

from syntaxhighlight import TokenClassNames

def createHighlighter(language):
    import cpp
    highlighter = cpp.HighlightCPP.create(language)
    if highlighter: return highlighter

    import generic
    highlighter = generic.HighlightGeneric.create(language)
    if highlighter: return highlighter

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
        self.output_file.close()

class HTMLOutputter(Outputter):
    def _writePart(self, token_type, content):
        self.output_file.write(
            "<b class='%s'>%s</b>"
            % (TokenClassNames[token_type], htmlutils.htmlify(content)))

    def _writePlain(self, content):
        self.output_file.write(htmlutils.htmlify(content))

    def _endLine(self):
        self.output_file.write("\n")

    def _flush(self):
        pass

class JSONOutputter(Outputter):
    def __init__(self, output_file):
        super(JSONOutputter, self).__init__(output_file)
        self.line = []

    def _writePart(self, token_type, content):
        if self.line \
                and isinstance(self.line[-1], list) \
                and self.line[-1][0] == token_type:
            self.line[-1][1] += content
        else:
            self.line.append([token_type, content])

    def _writePlain(self, content):
        self.line.append([None, content])

    def _endLine(self):
        self.output_file.write(textutils.json_encode(self.line) + "\n")
        self.line = []

    def _flush(self):
        if self.line:
            self._endLine()

def generateHighlight(repository_path, sha1, language, mode, output_file=None):
    highlighter = createHighlighter(language)
    if not highlighter: return False

    source = gitutils.Repository.readObject(repository_path, "blob", sha1)
    source = textutils.decode(source)

    if output_file:
        highlighter(source, output_file, None)
    else:
        output_path = syntaxhighlight.generateHighlightPath(sha1, language, mode)

        try: os.makedirs(os.path.dirname(output_path), 0750)
        except OSError as error:
            if error.errno == errno.EEXIST: pass
            else: raise

        output_file = open(output_path + ".tmp", "w")
        contexts_path = output_path + ".ctx"

        if mode == "json":
            outputter = JSONOutputter(output_file)
        else:
            outputter = HTMLOutputter(output_file)

        highlighter(source, outputter, contexts_path)

        output_file.close()

        os.chmod(output_path + ".tmp", 0660)
        os.rename(output_path + ".tmp", output_path)

    return True
