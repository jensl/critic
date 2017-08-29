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
import os.path
import bz2

import htmlutils
import textutils
import configuration
import diff.parse

LANGUAGES = set()

class TokenTypes:
    Operator = 1
    Identifier = 2
    Keyword = 3
    Character = 4
    String = 5
    Comment = 6
    Integer = 7
    Float = 8
    Preprocessing = 9

TokenClassNames = {
    TokenTypes.Operator: "op",
    TokenTypes.Identifier: "id",
    TokenTypes.Keyword: "kw",
    TokenTypes.Character: "chr",
    TokenTypes.String: "str",
    TokenTypes.Comment: "com",
    TokenTypes.Integer: "int",
    TokenTypes.Float: "fp",
    TokenTypes.Preprocessing: "pp",
}

class HighlightRequested(Exception):
    pass

def generateHighlightPath(sha1, language, mode="legacy"):
    if mode == "json":
        suffix = ".json"
    else:
        suffix = ""
    return os.path.join(configuration.services.HIGHLIGHT["cache_dir"], sha1[:2], sha1[2:] + "." + language + suffix)

def isHighlighted(sha1, language, mode="legacy"):
    path = generateHighlightPath(sha1, language, mode)
    return os.path.isfile(path) or os.path.isfile(path + ".bz2")

def wrap(raw_source, mode):
    if mode == "json":
        return "\n".join(textutils.json_encode([[None, line]])
                         for line in diff.parse.splitlines(raw_source))
    return htmlutils.htmlify(raw_source)

def readHighlight(repository, sha1, path, language, request=False, mode="legacy"):
    from request import requestHighlights

    async = mode == "json"
    source = None

    if language:
        path = generateHighlightPath(sha1, language, mode)

        if os.path.isfile(path):
            os.utime(path, None)
            source = open(path).read()
        elif os.path.isfile(path + ".bz2"):
            os.utime(path + ".bz2", None)
            source = bz2.BZ2File(path + ".bz2", "r").read()
        elif request:
            requestHighlights(repository, { sha1: (path, language) }, mode, async=async)
            if mode == "json":
                raise HighlightRequested()
            return readHighlight(repository, sha1, path, language, False, mode)

    if not source:
        source = wrap(textutils.decode(repository.fetch(sha1).data), mode)

    return source

# Import for side-effects: these modules add strings to the LANGUAGES set to
# indicate which languages they support highlighting.
import cpp
import generic
