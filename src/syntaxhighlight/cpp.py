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

class HighlightCPP:
    def highlightToken(self, token):
        if token.iskeyword():
            self.output.write("<b class='kw'>" + str(token) + "</b>")
        elif token.isidentifier():
            self.output.write("<b class='id'>" + str(token) + "</b>")
        elif token.iscomment():
            if str(token)[0:2] == "/*":
                lines = str(token).splitlines()
                self.output.write("\n".join(["<b class='com'>" + htmlutils.htmlify(line) + "</b>" for line in lines]))
            else:
                self.output.write("<b class='com'>" + htmlutils.htmlify(token) + "</b>")
        elif token.isppdirective():
            lines = str(token).split("\n")
            self.output.write("\n".join(["<b class='pp'>" + htmlutils.htmlify(line) + "</b>" for line in lines]))
        elif token.isspace():
            self.output.write(str(token))
        elif token.isconflictmarker():
            self.output.write(htmlutils.htmlify(token))
        else:
            if str(token)[0] == '"':
                self.output.write("<b class='str'>" + htmlutils.htmlify(token) + "</b>")
            elif str(token)[0] == "'":
                self.output.write("<b class='ch'>" + htmlutils.htmlify(token) + "</b>")
            elif token.isfloat():
                self.output.write("<b class='fp'>" + str(token) + "</b>")
            elif token.isint():
                self.output.write("<b class='int'>" + str(token) + "</b>")
            else:
                self.output.write("<b class='op'>" + htmlutils.htmlify(token) + "</b>")

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

    def __call__(self, source, output, contexts_path):
        source = source.encode("utf-8")
        self.output = output
        if contexts_path: self.contexts = open(contexts_path, "w")
        else: self.contexts = None
        self.processTokens(syntaxhighlight.clexer.tokenize(syntaxhighlight.clexer.split(source)))
        if contexts_path: self.contexts.close()

    @staticmethod
    def create(language):
        if language == "c++": return HighlightCPP()
        else: return None

syntaxhighlight.LANGUAGES.add("c++")
