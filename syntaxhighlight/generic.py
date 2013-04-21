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
import pygments.lexers
import pygments.token

import htmlutils

LANGUAGES = { "python": pygments.lexers.PythonLexer,
              "perl": pygments.lexers.PerlLexer,
              "java": pygments.lexers.JavaLexer,
              "ruby": pygments.lexers.RubyLexer,
              "php": pygments.lexers.PhpLexer,
              "makefile": pygments.lexers.MakefileLexer,
              "javascript": pygments.lexers.JavascriptLexer,
              "sql": pygments.lexers.SqlLexer,
              "objective-c": pygments.lexers.ObjectiveCLexer,
              "xml": pygments.lexers.XmlLexer }

class HighlightGeneric:
    def __init__(self, lexer):
        self.lexer = lexer

    def highlightToken(self, token, value):
        def tag(cls, value): return "<b class='%s'>%s</b>" % (cls, htmlutils.htmlify(value))
        def tagm(cls, value):
            if value == "\n": return value
            else:
                res = []
                for line in value.splitlines():
                    if line: res.append(tag(cls, line))
                    else: res.append(line)
                if value.endswith("\n"): res.append("")
                return "\n".join(res)

        value = value.encode("utf-8")

        if token in pygments.token.Token.Punctuation or token in pygments.token.Token.Operator:
            self.output.write(tag("op", value))
        elif token in pygments.token.Token.Name or token in pygments.token.Token.String.Symbol:
            self.output.write(tag("id", value))
        elif token in pygments.token.Token.Keyword:
            self.output.write(tag("kw", value))
        elif token in pygments.token.Token.String:
            self.output.write(tagm("str", value))
        elif token in pygments.token.Token.Comment:
            self.output.write(tagm("com", value))
        elif token in pygments.token.Token.Number.Integer:
            self.output.write(tag("int", value))
        elif token in pygments.token.Token.Number.Float:
            self.output.write(tag("fp", value))
        else:
            self.output.write(htmlutils.htmlify(value))

    def __call__(self, source, output_file, contexts_path):
        try: source = source.decode("utf-8")
        except: source = source.decode("latin-1")

        self.output = output_file

        blocks = re.split("^((?:<<<<<<<|>>>>>>>)[^\n]*\n)", source, flags=re.MULTILINE)

        in_conflict = False

        for index, block in enumerate(blocks):
            if (index & 1) == 0:
                if in_conflict:
                    blocks = re.split("^(=======[^\n]*\n)", block, flags=re.MULTILINE)
                else:
                    blocks = [block]

                for index, block in enumerate(blocks):
                    if (index & 1) == 0:
                        if block:
                            for token, value in self.lexer.get_tokens(block):
                                self.highlightToken(token, value)
                    else:
                        assert block[0] == "="
                        self.output.write(htmlutils.htmlify(block))
            else:
                assert block[0] == "<" or block[0] == ">"
                self.output.write(htmlutils.htmlify(block))
                in_conflict = block[0] == "<"

    @staticmethod
    def create(language):
        lexer = LANGUAGES.get(language)
        if lexer: return HighlightGeneric(lexer(stripnl=False))
        else: return None

import syntaxhighlight

syntaxhighlight.LANGUAGES.update(LANGUAGES.keys())
