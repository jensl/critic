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

# FIXME: Discontinue this highlighter.
# type: ignore

from __future__ import annotations
from typing import Any, Optional

from .tokentypes import TokenTypes
from .languages import LANGUAGES

from .clexer import CLexerGroupingException, group1, flatten, split, tokenize, Token
from .context import MIN_CONTEXT_LENGTH
from .outputter import Outputter
from .tokentypes import TokenTypes


class HighlightCPP:
    def highlightToken(self, token: Token) -> None:
        if token.iskeyword():
            self.outputter.writeSingleline(TokenTypes.Keyword, str(token))
        elif token.isidentifier():
            self.outputter.writeSingleline(TokenTypes.Identifier, str(token))
        elif token.iscomment():
            if str(token)[0:2] == "/*":
                self.outputter.writeMultiline(TokenTypes.Comment, str(token))
            else:
                self.outputter.writeSingleline(TokenTypes.Comment, str(token))
        elif token.isppdirective():
            self.outputter.writeMultiline(TokenTypes.Preprocessing, str(token))
        elif token.isspace():
            self.outputter.writePlain(str(token))
        elif token.isconflictmarker():
            self.outputter.writePlain(str(token))
        elif str(token)[0] == '"':
            self.outputter.writeSingleline(TokenTypes.String, str(token))
        elif str(token)[0] == "'":
            self.outputter.writeSingleline(TokenTypes.Character, str(token))
        elif token.isfloat():
            self.outputter.writeSingleline(TokenTypes.Float, str(token))
        elif token.isint():
            self.outputter.writeSingleline(TokenTypes.Integer, str(token))
        elif token.isbyteordermark():
            self.outputter.writePlain("\ufeff")
        else:
            self.outputter.writeSingleline(TokenTypes.Operator, str(token))

    def outputContext(self, tokens, terminator):
        def spaceBetween(first, second):
            # Never insert spaces around the :: operator.
            if first == "::" or second == "::":
                return False

            # Always a space after a comma.
            if first == ",":
                return True

            # Always a space before a keyword or identifier, unless preceded by *, & or (.
            if second.iskeyword() or second.isidentifier():
                return str(first) not in ("*", "&", "(")

            # Always a space before a * or &, unless preceded by (another) *.
            if (second == "*" or second == "&") and first != "*":
                return True

            # Always spaces around equal signs.
            if first == "=" or second == "=":
                return True

            # No spaces between by default.
            return False

        first_line = tokens[-1].line() + 1
        last_line = terminator.line()

        if last_line - first_line >= MIN_CONTEXT_LENGTH:
            previous = tokens[0]
            value = str(previous)

            for token in tokens[1:]:
                if token.isspace() or token.iscomment():
                    continue
                if spaceBetween(previous, token):
                    value += " "
                value += str(token)
                previous = token

            self.contexts.append((first_line - 1, last_line - 1, value))

    def processTokens(self, tokens):
        currentContexts = []
        nextContext = []
        nextContextClosed = False
        level = 0

        for token in tokens:
            self.highlightToken(token)

            if (
                token.isspace()
                or token.iscomment()
                or token.isppdirective()
                or token.isconflictmarker()
            ):
                pass
            elif token.iskeyword():
                if str(token) in (
                    "if",
                    "else",
                    "for",
                    "while",
                    "do",
                    "switch",
                    "return",
                    "break",
                    "continue",
                ):
                    nextContext = None
                    nextContextClosed = True
                elif not nextContextClosed:
                    nextContext.append(token)
            elif token.isidentifier():
                if not nextContextClosed:
                    nextContext.append(token)
            elif token == "{":
                if nextContext:
                    currentContexts.append([nextContext, level])
                    nextContext = []
                    nextContextClosed = False
                level += 1
            elif token == "}":
                level -= 1
                if currentContexts and currentContexts[-1][1] == level:
                    thisContext = currentContexts.pop()
                    self.outputContext(thisContext[0], token)
                nextContext = []
                nextContextClosed = False
            elif nextContext:
                if token == "," and not nextContextClosed:
                    nextContext = None
                    nextContextClosed = True
                elif token == ":":
                    nextContextClosed = True
                elif token == ";":
                    nextContext = []
                    nextContextClosed = False
                elif token == "(":
                    if not nextContextClosed:
                        nextContext.append(token)
                        try:
                            group, token = group1(tokens, ")")
                            group = list(flatten(group)) + [token]
                            nextContext.extend(group)
                            for token in group:
                                self.highlightToken(token)
                        except CLexerGroupingException as error:
                            for token in error.tokens():
                                self.highlightToken(token)
                            nextContext = []
                            nextContextClosed = False
                elif not nextContextClosed:
                    nextContext.append(token)

    outputter: Outputter

    def __call__(self, source: str, outputter: Outputter) -> Any:
        self.outputter = outputter
        self.contexts = []
        self.processTokens(tokenize(split(source)))
        return self.contexts

    @staticmethod
    def create(language: str) -> Optional[HighlightCPP]:
        if language == "c/c++":
            return HighlightCPP()
        else:
            return None


LANGUAGES.add("c/c++")
