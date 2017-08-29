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

try:
    import pygments.lexers
    import pygments.token
except ImportError:
    LANGUAGES = {}
else:
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

import htmlutils

from syntaxhighlight import TokenTypes

class HighlightGeneric:
    def __init__(self, lexer):
        self.lexer = lexer

    def highlightToken(self, token, value):
        value = value.encode("utf-8")

        if token in pygments.token.Token.Punctuation or token in pygments.token.Token.Operator:
            self.outputter.writeSingleline(TokenTypes.Operator, value)
        elif token in pygments.token.Token.Name or token in pygments.token.Token.String.Symbol:
            self.outputter.writeSingleline(TokenTypes.Identifier, value)
        elif token in pygments.token.Token.Keyword:
            self.outputter.writeSingleline(TokenTypes.Keyword, value)
        elif token in pygments.token.Token.String:
            self.outputter.writeMultiline(TokenTypes.String, value)
        elif token in pygments.token.Token.Comment:
            self.outputter.writeMultiline(TokenTypes.Comment, value)
        elif token in pygments.token.Token.Number.Integer:
            self.outputter.writeSingleline(TokenTypes.Integer, value)
        elif token in pygments.token.Token.Number.Float:
            self.outputter.writeSingleline(TokenTypes.Float, value)
        else:
            self.outputter.writePlain(value)

    def __call__(self, source, outputter, contexts_path):
        self.outputter = outputter

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
                        self.outputter.writePlain(block)
            else:
                assert block[0] == "<" or block[0] == ">"
                self.outputter.writePlain(block)
                in_conflict = block[0] == "<"

    @staticmethod
    def create(language):
        lexer = LANGUAGES.get(language)
        if lexer: return HighlightGeneric(lexer(stripnl=False))
        else: return None

import syntaxhighlight

syntaxhighlight.LANGUAGES.update(LANGUAGES.keys())
