from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Tuple, cast

logger = logging.getLogger(__name__)

from critic import api
from critic.base.profiling import Profiler
from critic import dbaccess
from critic import pubsub
from critic.background.differenceengine.protocol import SyntaxHighlighFile
from critic.syntaxhighlight.generate import LanguageNotSupported, generate

from .databaseupdater import DatabaseUpdater
from .error import Error
from .readsource import read_source
from .session import Session, Command


SEMAPHORE = asyncio.Semaphore(10)


@dataclass
class HighlightFile:
    file_id: int
    is_highlighted: bool


def ensure_highlightfile(
    request: SyntaxHighlighFile.Request,
) -> Command[HighlightFile]:
    async def execute(critic: api.critic.Critic) -> HighlightFile:
        async with api.critic.Query[Tuple[int, bool]](
            critic,
            """SELECT id, highlighted
                 FROM highlightfiles
                WHERE repository={repository_id}
                  AND sha1={sha1}
                  AND language={language_id}
                  AND conflicts={conflicts}""",
            repository_id=request.repository_id,
            sha1=request.source.sha1,
            language_id=request.language_id,
            conflicts=request.conflicts,
        ) as result:
            try:
                file_id, is_highlighted = await result.one()
                return HighlightFile(file_id, is_highlighted)
            except dbaccess.ZeroRowsInResult:
                pass
        async with critic.transaction() as cursor:
            file_id = await cursor.insert(
                "highlightfiles",
                dbaccess.parameters(
                    repository=request.repository_id,
                    sha1=request.source.sha1,
                    language=request.language_id,
                    conflicts=request.conflicts,
                ),
                returning="id",
                value_type=int,
            )
        return HighlightFile(file_id, False)

    return execute


async def handle_syntaxhighlightfile(
    loop: asyncio.AbstractEventLoop,
    payload: object,
    session: Session,
    database_updater: DatabaseUpdater,
    profiler: Profiler,
) -> SyntaxHighlighFile.Response:
    assert isinstance(payload, SyntaxHighlighFile.Request)

    request = cast(SyntaxHighlighFile.Request, payload)

    highlightfile = await session.execute(ensure_highlightfile(request))

    if highlightfile.is_highlighted:
        return SyntaxHighlighFile.Response(highlightfile.file_id)

    async with SEMAPHORE:
        source = await read_source(request.source)

        try:
            lines, contexts = await loop.run_in_executor(
                None, generate, source, request.language_label
            )
        except LanguageNotSupported:
            raise Error(f"{request.language_label}: language not supported")

    await database_updater.push(
        (
            """
            UPDATE highlightfiles
               SET highlighted=TRUE,
                   requested=FALSE
             WHERE id=%s
            """,
            [(highlightfile.file_id,)],
        ),
        (
            """
            INSERT INTO highlightlines (
              file, line, data
            ) VALUES (
              %s, %s, %s
            ) ON CONFLICT DO NOTHING
            """,
            ((highlightfile.file_id, index, data) for index, data in enumerate(lines)),
        ),
        (
            """
            INSERT INTO codecontexts (
              sha1, language, first_line, last_line, context
            ) VALUES (
              %s, %s, %s, %s, %s
            ) ON CONFLICT DO NOTHING
            """,
            (
                (
                    request.source.sha1,
                    request.language_id,
                    first_line,
                    last_line,
                    context,
                )
                for first_line, last_line, context in contexts
            ),
        ),
    )

    logger.info("Highlighted %s [%s]", request.source.sha1, request.language_label)

    return SyntaxHighlighFile.Response(highlightfile.file_id)
