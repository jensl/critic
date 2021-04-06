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

from collections import defaultdict
import contextlib
from dataclasses import dataclass
import logging
import time
from typing import Dict, Iterator, List

logger = logging.getLogger(__name__)


@dataclass
class CheckData:
    count: int = 0
    maximum: float = 0
    total: float = 0

    def add(self, duration: float) -> None:
        self.count += 1
        if duration > self.maximum:
            self.maximum = duration
        self.total += duration


class Profiler:
    class Check:
        def __init__(self, profiler: Profiler, title: str):
            self.__profiler = profiler
            self.__title = title
            self.__begin = time.time()

        def stop(self) -> None:
            self.__profiler.add(self.__title, self.__begin, time.time())

    __checks: Dict[str, CheckData]

    def __init__(self):
        self.__previous = time.time()
        self.__checks = defaultdict(CheckData)

    def add(self, title: str, begin: float, end: float) -> None:
        self.__checks[title].add(end - begin)
        self.__previous = end

    def start(self, title: str) -> Profiler.Check:
        return Profiler.Check(self, title)

    # def check(self, title: str) -> None:
    #     self.add(title, self.__previous, time.time())

    def output(self) -> str:
        log = ""
        count = 0
        maximum = 0.0
        total = 0.0

        title_width = max(list(map(len, ["TOTAL", *self.__checks.keys()])))
        format = "  %%-%ds : %%5d %%8.2f %%8.2f %%8.2f\n" % title_width

        for title, check in sorted(
            self.__checks.items(), key=lambda item: item[1].total, reverse=True
        ):
            log += format % (
                title,
                check.count,
                (check.total * 1000) / check.count,
                check.maximum * 1000,
                check.total * 1000,
            )
            count += check.count
            if check.maximum > maximum:
                maximum = check.maximum
            total += check.total

        return (
            log
            + "\n"
            + format
            % (
                "TOTAL",
                count,
                (total * 1000) / count if count else 0,
                maximum * 1000,
                total * 1000,
            )
        )

    @contextlib.contextmanager
    def check(self, title: str) -> Iterator[None]:
        check = self.start(title)
        try:
            yield
        finally:
            check.stop()


# def formatDBProfiling(db):
#     lines = [
#         "         | TIME (milliseconds)    | ROWS                   |",
#         "   Count | Accumulated |  Maximum | Accumulated |  Maximum | Query",
#         "  -------|-------------|----------|-------------|----------|-------",
#     ]
#     items = sorted(db.profiling.items(), key=lambda item: item[1][1], reverse=True)

#     total_count = 0
#     total_accumulated_ms = 0.0
#     total_accumulated_rows = 0

#     for (
#         item,
#         (count, accumulated_ms, maximum_ms, accumulated_rows, maximum_rows),
#     ) in items:
#         total_count += count
#         total_accumulated_ms += accumulated_ms

#         if accumulated_rows is None:
#             lines.append(
#                 "  %6d | %11.4f | %8.4f |             |          | %s"
#                 % (count, accumulated_ms, maximum_ms, re.sub(r"\s+", " ", item))
#             )
#         else:
#             total_accumulated_rows += accumulated_rows

#             lines.append(
#                 "  %6d | %11.4f | %8.4f | %11d | %8d | %s"
#                 % (
#                     count,
#                     accumulated_ms,
#                     maximum_ms,
#                     accumulated_rows,
#                     maximum_rows,
#                     re.sub(r"\s+", " ", item),
#                 )
#             )

#     lines.insert(
#         3,
#         (
#             "  %6d | %11.4f |          | %11d |          | TOTAL"
#             % (total_count, total_accumulated_ms, total_accumulated_rows)
#         ),
#     )

#     return "\n".join(lines)


@contextlib.contextmanager
def timed(
    label: str, acceptable_wall: int = 500, acceptable_cpu: int = 100
) -> Iterator[None]:
    before_wall = time.clock_gettime(time.CLOCK_REALTIME)
    before_cpu = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)
    try:
        yield
    finally:
        after_wall = time.clock_gettime(time.CLOCK_REALTIME)
        after_cpu = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)
        duration_wall = (after_wall - before_wall) * 1000
        duration_cpu = (after_cpu - before_cpu) * 1000
        if (acceptable_wall and duration_wall > acceptable_wall) or (
            acceptable_cpu and duration_cpu > acceptable_cpu
        ):
            logger.warning(
                "%s: wall=%.3f ms, cpu=%.3f ms", label, duration_wall, duration_cpu
            )
