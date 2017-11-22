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

import bz2
import json
import logging
import os
import os.path
from typing import Set

logger = logging.getLogger(__name__)

from critic import api
from critic import background
from critic import diff
from critic import textutils

LANGUAGES: Set[str] = set()


class TokenTypes:
    Whitespace = api.filediff.PART_TYPE_NEUTRAL
    Operator = api.filediff.PART_TYPE_OPERATOR
    Identifier = api.filediff.PART_TYPE_IDENTIFIER
    Keyword = api.filediff.PART_TYPE_KEYWORD
    Character = api.filediff.PART_TYPE_CHARACTER
    String = api.filediff.PART_TYPE_STRING
    Comment = api.filediff.PART_TYPE_COMMENT
    Integer = api.filediff.PART_TYPE_INTEGER
    Float = api.filediff.PART_TYPE_FLOAT
    Preprocessing = api.filediff.PART_TYPE_PREPROCESSING


TokenClassNames = {
    TokenTypes.Whitespace: None,
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

CACHE_PATH = None


class HighlightRequested(Exception):
    pass


def cachePath():
    global CACHE_PATH
    if CACHE_PATH is None:
        CACHE_PATH = api.critic.settings().paths.cache
    return CACHE_PATH


def generateHighlightPath(sha1, language, conflicts, mode="legacy"):
    assert mode != "binary"  # Stored in the database.
    suffix = ".conflicts" if conflicts else ""
    if mode == "json":
        suffix += ".json"
    return os.path.join(
        cachePath(), "highlight", sha1[:2], sha1[2:] + "." + language + suffix
    )


def isHighlighted(sha1, language, conflicts, mode="legacy"):
    assert mode != "binary"  # Stored in the database.
    if not language:
        return False
    path = generateHighlightPath(sha1, language, conflicts, mode)
    return os.path.isfile(path) or os.path.isfile(path + ".bz2")


def wrapLineJSON(raw_line):
    return [[textutils.decode(raw_line)]]


def wrap(raw_source, mode):
    return "\n".join(
        json.dumps(wrapLineJSON(line)) for line in diff.parse.splitlines(raw_source)
    )


def processRanges(source, ranges, process_line=lambda line: line):
    offset = 0
    current = 0
    for begin, end in ranges:
        lines = []
        while current < begin:
            offset = source.index(b"\n", offset) + 1
            current += 1
        while current < end:
            line_end = source.index(b"\n", offset)
            lines.append(process_line(source[offset:line_end]))
            offset = line_end + 1
            current += 1
        yield [begin, end, lines]


def readHighlightFile(sha1, language, conflicts, mode):
    if language:
        path = generateHighlightPath(sha1, language, conflicts, mode)

        if os.path.isfile(path):
            os.utime(path, None)
            with open(path, "rb") as file:
                return file.read()

        if os.path.isfile(path + ".bz2"):
            os.utime(path + ".bz2", None)
            with bz2.BZ2File(path + ".bz2", "rb") as file:
                return file.read()

    return None


async def requestHighlight(repository, file, sha1, language):
    critic = repository.critic

    async with critic.transaction() as cursor:
        async with cursor.query(
            """SELECT id
                 FROM highlightlanguages
                WHERE label={language}""",
            language=language,
        ) as result:
            try:
                language_id = await result.scalar()
            except cursor.ZeroRowsInResult:
                return False

        async with cursor.query(
            """SELECT id, highlighted, requested
                 FROM highlightfiles
                WHERE repository={repository}
                  AND sha1={sha1}
                  AND language={language_id}
                  AND NOT conflicts""",
            repository=repository,
            sha1=sha1,
            language_id=language_id,
        ) as result:
            try:
                highlightfile_id, highlighted, requested = await result.one()
            except cursor.ZeroRowsInResult:
                highlightfile_id = None
                highlighted = False
                requested = True  # We will request implicitly when inserting
                # a row into |highlightfiles| below.

        if highlightfile_id is None:
            async with cursor.query(
                """INSERT
                     INTO highlightfiles (
                            repository, sha1, language, conflicts
                          )
                   VALUES ({repository}, {sha1}, {language_id}, FALSE)""",
                repository=repository,
                sha1=sha1,
                language_id=language_id,
                returning="id",
            ) as result:
                highlightfile_id = await result.scalar()
            customhighlightrequest_id = None
        else:
            if not highlighted and not requested:
                await cursor.execute(
                    """UPDATE highlightfiles
                          SET requested=TRUE
                        WHERE id={file}""",
                    file=highlightfile_id,
                )

            async with cursor.query(
                """SELECT id
                     FROM customhighlightrequests
                    WHERE file={file}""",
                file=highlightfile_id,
            ) as result:
                customhighlightrequest_id = await result.maybe_scalar()

        if customhighlightrequest_id is None:
            await cursor.execute(
                """INSERT
                     INTO customhighlightrequests (file)
                   VALUES ({file})""",
                file=highlightfile_id,
            )
        else:
            await cursor.execute(
                """UPDATE customhighlightrequests
                      SET last_access=NOW()
                    WHERE id={customhighlightrequest_id}""",
                customhighlightrequest_id=customhighlightrequest_id,
            )

    if not highlighted:
        await background.utils.wakeup("differenceengine")

    return True


from . import generate
from . import language

# Import for side-effects: these modules add strings to the LANGUAGES set to
# indicate which languages they support highlighting.
from . import cpp
from . import generic

__all__ = ["request", "generate", "language", "cpp", "generic"]
