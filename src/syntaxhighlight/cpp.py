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

import syntaxhighlight
import syntaxhighlight.clexer
import htmlutils
import configuration

from syntaxhighlight import TokenTypes

class HighlightCPP:
    def highlightToken(self, token):
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
        if not self.contexts: return

        def spaceBetween(first, second):
            # Never insert spaces around the :: operator.
            if first == '::' or second == '::':
                return False

            # Always a space after a comma.
            if first == ',':
                return True

            # Always a space before a keyword or identifier, unless preceded by *, & or (.
            if second.iskeyword() or second.isidentifier():
                return str(first) not in ('*', '&', '(')

            # Always a space before a * or &, unless preceded by (another) *.
            if (second == '*' or second == '&') and first != '*':
                return True

            # Always spaces around equal signs.
            if first == '=' or second == '=':
                return True

            # No spaces between by default.
            return False

        first_line = tokens[-1].line() + 1
        last_line = terminator.line()

        if last_line - first_line >= configuration.services.HIGHLIGHT["min_context_length"]:
            previous = tokens[0]
            context = str(previous)

            for token in tokens[1:]:
                if token.isspace() or token.iscomment(): continue
                if spaceBetween(previous, token): context += " "
                context += str(token)
                previous = token

            self.contexts.write("%d %d %s\n" % (first_line, last_line, context))

    def processTokens(self, tokens):
        currentContexts = []
        nextContext = []
        nextContextClosed = False
        level = 0

        for token in tokens:
            self.highlightToken(token)

            if token.isspace() or token.iscomment() or token.isppdirective() or token.isconflictmarker():
                pass
            elif token.iskeyword():
                if str(token) in ("if", "else", "for", "while", "do", "switch", "return", "break", "continue"):
                    nextContext = None
                    nextContextClosed = True
                elif not nextContextClosed:
                    nextContext.append(token)
            elif token.isidentifier():
                if not nextContextClosed:
                    nextContext.append(token)
            elif token == '{':
                if nextContext:
                    currentContexts.append([nextContext, level])
                    nextContext = []
                    nextContextClosed = False
                level += 1
            elif token == '}':
                level -= 1
                if currentContexts and currentContexts[-1][1] == level:
                    thisContext = currentContexts.pop()
                    self.outputContext(thisContext[0], token)
                nextContext = []
                nextContextClosed = False
            elif nextContext:
                if token == ',' and not nextContextClosed:
                    nextContext = None
                    nextContextClosed = True
                elif token == ':':
                    nextContextClosed = True
                elif token == ';':
                    nextContext = []
                    nextContextClosed = False
                elif token == '(':
                    if not nextContextClosed:
                        nextContext.append(token)
                        try:
                            group, token = syntaxhighlight.clexer.group1(tokens, ')')
                            group = list(syntaxhighlight.clexer.flatten(group)) + [token]
                            nextContext.extend(group)
                            for token in group: self.highlightToken(token)
                        except syntaxhighlight.clexer.CLexerGroupingException as error:
                            for token in error.tokens(): self.highlightToken(token)
                            nextContext = []
                            nextContextClosed = False
                elif not nextContextClosed:
                    nextContext.append(token)

    def __call__(self, source, outputter, contexts_path):
        source = source.encode("utf-8")
        self.outputter = outputter
        if contexts_path: self.contexts = open(contexts_path, "w")
        else: self.contexts = None
        self.processTokens(syntaxhighlight.clexer.tokenize(syntaxhighlight.clexer.split(source)))
        if contexts_path: self.contexts.close()

    @staticmethod
    def create(language):
        if language == "c++": return HighlightCPP()
        else: return None

syntaxhighlight.LANGUAGES.add("c++")
