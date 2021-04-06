from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Sequence, Tuple

logger = logging.getLogger(__name__)

from critic.base.profiling import Profiler
from critic.background.differenceengine.protocol import AnalyzeChangedLines, Block
from critic.diff.parse import splitlines

from .analyzechunk import analyzeChunk
from .databaseupdater import DatabaseUpdater
from .readsource import read_sources
from .session import Session


def extract_lines(lines: Sequence[str], offset: int, length: int) -> Sequence[str]:
    assert length != 0 and offset + length <= len(
        lines
    ), f"{lines=} {offset=} {length=}"
    return lines[offset : offset + length]


def extract_old_lines(lines: Sequence[str], block: Block) -> Sequence[str]:
    return extract_lines(lines, block.old_offset, block.old_length)


def extract_new_lines(lines: Sequence[str], block: Block) -> Sequence[str]:
    return extract_lines(lines, block.new_offset, block.new_length)


SEMAPHORE = asyncio.Semaphore(10)


async def handle_analyzechangedlines(
    loop: asyncio.AbstractEventLoop,
    payload: object,
    session: Session,
    database_updater: DatabaseUpdater,
    profiler: Profiler,
) -> AnalyzeChangedLines.Response:
    assert isinstance(payload, AnalyzeChangedLines.Request)

    request = payload

    async def fetch_lines() -> Tuple[Sequence[str], Sequence[str]]:
        with profiler.check("analyzechangedlines: read_sources"):
            old_source, new_source = await read_sources(
                request.old_source, request.new_source
            )

        with profiler.check("analyzechangedlines: splitlines"):
            return splitlines(old_source), splitlines(new_source)

    async def analyze_blocks() -> Sequence[Sequence[object]]:
        old_lines, new_lines = await fetch_lines()

        values: List[Sequence[object]] = []

        with profiler.check("analyzechangedlines: process blocks"):
            for block in request.blocks:
                with profiler.check("analyzechangedlines: single block"):
                    old_block = extract_old_lines(old_lines, block)
                    new_block = extract_new_lines(new_lines, block)

                    analysis = await loop.run_in_executor(
                        None, analyzeChunk, old_block, new_block
                    )

                    values.append(
                        (
                            analysis or "",
                            request.changeset_id,
                            request.file_id,
                            block.index,
                        )
                    )

        return values

    before = time.time()

    async with SEMAPHORE:
        values = await analyze_blocks()

    with profiler.check("analyzechangedlines: update database"):
        await database_updater.push(
            (
                """
                UPDATE changesetchangedlines
                   SET analysis=%s
                 WHERE changeset=%s
                   AND file=%s
                   AND index=%s
                """,
                values,
            )
        )

    after = time.time()

    return AnalyzeChangedLines.Response(after - before)
