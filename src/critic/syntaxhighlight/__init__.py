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

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic import background
from critic import dbaccess
from critic.gitaccess import SHA1

from .tokentypes import TokenTypes


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


class HighlightRequested(Exception):
    pass


async def requestHighlight(
    repository: api.repository.Repository,
    file: Optional[api.file.File],
    sha1: SHA1,
    language: str,
) -> bool:
    critic = repository.critic

    async with critic.transaction() as cursor:
        async with dbaccess.Query[int](
            cursor,
            """SELECT id
                 FROM highlightlanguages
                WHERE label={language}""",
            language=language,
        ) as language_result:
            try:
                language_id = await language_result.scalar()
            except cursor.ZeroRowsInResult:
                return False

        highlightfile_id: Optional[int]

        async with dbaccess.Query[Tuple[int, bool, bool]](
            cursor,
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
            highlightfile_id = await cursor.insert(
                "highlightfiles",
                dbaccess.parameters(
                    repository=repository, sha1=sha1, language=language_id
                ),
                returning="id",
                value_type=int,
            )
            customhighlightrequest_id = None
        else:
            if not highlighted and not requested:
                await cursor.execute(
                    """UPDATE highlightfiles
                          SET requested=TRUE
                        WHERE id={file}""",
                    file=highlightfile_id,
                )

            async with dbaccess.Query[int](
                cursor,
                """SELECT id
                     FROM customhighlightrequests
                    WHERE file={file}""",
                file=highlightfile_id,
            ) as customhighlightrequest_result:
                customhighlightrequest_id = (
                    await customhighlightrequest_result.maybe_scalar()
                )

        if customhighlightrequest_id is None:
            await cursor.insert(
                "customhighlightrequests", dbaccess.parameters(file=highlightfile_id)
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
