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

from __future__ import annotations

import re
from typing import Any, Optional

from .outputter import Outputter

try:
    import pygments.lexers
    import pygments.token
except ImportError:
    SUPPORTED_LANGUAGES = {}
else:
    SUPPORTED_LANGUAGES = {
        "c/c++": "cpp",
        "python": "python3",
        "perl": "perl",
        "java": "java",
        "ruby": "ruby",
        "php": "php",
        "makefile": "makefile",
        "markdown": "md",
        "javascript": "javascript",
        "json": "javascript",
        "sql": "sql",
        "objective-c": "objective-c",
        "yaml": "yaml",
        "xml": "xml",
        "go": "go",
        "css": "css",
        "scss": "scss",
    }

from .tokentypes import TokenTypes


class HighlightGeneric:
    outputter: Outputter

    def __init__(self, lexer: Any):
        self.lexer = lexer

    def highlightToken(self, token: Any, value: str) -> None:
        if (
            token in pygments.token.Token.Keyword
            or token in pygments.token.Token.Operator.Word
        ):
            self.outputter.writeSingleline(TokenTypes.Keyword, value)
        elif (
            token in pygments.token.Token.Punctuation
            or token in pygments.token.Token.Operator
        ):
            self.outputter.writeSingleline(TokenTypes.Operator, value)
        elif (
            token in pygments.token.Token.Name
            or token in pygments.token.Token.String.Symbol
        ):
            self.outputter.writeSingleline(TokenTypes.Identifier, value)
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

    def __call__(self, source: str, outputter: Outputter) -> Any:
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

        return []

    @staticmethod
    def create(language: str) -> Optional[HighlightGeneric]:
        lexer_name = SUPPORTED_LANGUAGES.get(language)
        if not lexer_name:
            return None
        lexer = None
        # if lexer_name == "javascript":
        #     try:
        #         from pygmentslexerbabylon import BabylonLexer
        #     except ImportError:
        #         pass
        #     else:
        #         lexer = BabylonLexer(stripnl=False)
        if lexer is None:
            try:
                lexer = pygments.lexers.get_lexer_by_name(lexer_name, stripnl=False)
            except pygments.util.ClassNotFound:
                return None
        return HighlightGeneric(lexer)


from .languages import LANGUAGES

LANGUAGES.update(SUPPORTED_LANGUAGES.keys())
