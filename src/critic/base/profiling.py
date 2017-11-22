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

import contextlib
import logging
import re
import time

logger = logging.getLogger(__name__)


class Profiler:
    class Check:
        def __init__(self, profiler, title):
            self.__profiler = profiler
            self.__title = title
            self.__begin = time.time()

        def stop(self):
            self.__profiler.add(self.__title, self.__begin, time.time())

    def __init__(self):
        self.__previous = time.time()
        self.__checks = []
        self.__table = {}

    def add(self, title, begin, end):
        if title not in self.__table:
            self.__checks.append(title)
            self.__table[title] = 0

        self.__table[title] += end - begin
        self.__previous = end

    def start(self, title):
        return Profiler.Check(self, title)

    def check(self, title):
        self.add(title, self.__previous, time.time())

    def output(self, db=None, user=None, target=None):
        log = ""
        total = 0.0

        title_width = max(list(map(len, self.__checks)))
        format = "  %%-%ds : %%8.2f\n" % title_width

        for title, duration in sorted(
            self.__table.items(), key=lambda item: item[1], reverse=True
        ):
            log += format % (title, self.__table[title] * 1000)
            total += self.__table[title]

        log += "\n" + format % ("TOTAL", total * 1000)

        if (
            db
            and user
            and target
            and user.getPreference(db, "debug.profiling.pageGeneration")
        ):
            target.comment("\n\n" + log + "\n")

        return log


def formatDBProfiling(db):
    lines = [
        "         | TIME (milliseconds)    | ROWS                   |",
        "   Count | Accumulated |  Maximum | Accumulated |  Maximum | Query",
        "  -------|-------------|----------|-------------|----------|-------",
    ]
    items = sorted(db.profiling.items(), key=lambda item: item[1][1], reverse=True)

    total_count = 0
    total_accumulated_ms = 0.0
    total_accumulated_rows = 0

    for (
        item,
        (count, accumulated_ms, maximum_ms, accumulated_rows, maximum_rows),
    ) in items:
        total_count += count
        total_accumulated_ms += accumulated_ms

        if accumulated_rows is None:
            lines.append(
                "  %6d | %11.4f | %8.4f |             |          | %s"
                % (count, accumulated_ms, maximum_ms, re.sub(r"\s+", " ", item))
            )
        else:
            total_accumulated_rows += accumulated_rows

            lines.append(
                "  %6d | %11.4f | %8.4f | %11d | %8d | %s"
                % (
                    count,
                    accumulated_ms,
                    maximum_ms,
                    accumulated_rows,
                    maximum_rows,
                    re.sub(r"\s+", " ", item),
                )
            )

    lines.insert(
        3,
        (
            "  %6d | %11.4f |          | %11d |          | TOTAL"
            % (total_count, total_accumulated_ms, total_accumulated_rows)
        ),
    )

    return "\n".join(lines)


@contextlib.contextmanager
def timed(label, acceptable_wall=500, acceptable_cpu=100):
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
