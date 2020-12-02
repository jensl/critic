from __future__ import annotations

import contextlib
import logging
import sys
import textwrap
import time
from typing import ClassVar, Iterator, List, Tuple

from .arguments import Arguments


class OutputManager(logging.Handler):
    instance: ClassVar[OutputManager]

    activities: List[Tuple[str, float]]

    def __init__(self, arguments: Arguments):
        super().__init__()
        OutputManager.instance = self
        self.quiet = arguments.quiet
        self.activities = []
        self.partial_line = False
        self.need_blankline = False
        self.debug_formatter = logging.Formatter("DEBUG: %(name)s: %(message)s")
        self.info_formatter = logging.Formatter("%(message)s")
        self.other_formatter = logging.Formatter("%(levelname)s: %(message)s")
        self.system_formatter = logging.Formatter(
            "%(levelname)s: %(name)s: %(message)s"
        )

    def indent(self, message: str) -> str:
        return textwrap.indent(message, "  " * len(self.activities))

    def output(self, message: str, *, continue_partial_line: bool = False) -> None:
        if self.partial_line and not continue_partial_line:
            sys.stderr.write("\n")
        if len(message.splitlines()) > 1:
            self.blankline()
        if continue_partial_line:
            sys.stderr.write(message)
        else:
            sys.stderr.write(self.indent(message))
        sys.stderr.flush()
        self.partial_line = not message.endswith("\n")
        self.need_blankline = not (message == "\n" or message.endswith("\n\n"))

    @staticmethod
    def blankline(*, forced: bool = False) -> None:
        if OutputManager.instance.need_blankline or forced:
            OutputManager.instance.output("\n")
            OutputManager.instance.need_blankline = False

    def start_activity(self, title: str, *, blankline_before: bool = False) -> None:
        if not self.quiet:
            if blankline_before:
                self.blankline()
            self.output(title + " ...")
            self.activities.append((title, time.time()))

    def end_activity(
        self,
        expected_title: str,
        *,
        blankline_after: bool = False,
        silent: bool = False
    ) -> None:
        if not self.quiet:
            title, started = self.activities.pop()
            assert title == expected_title
            if silent:
                return
            if not self.partial_line:
                self.output(title + ":")
            self.output(
                " done in %.2fs.\n" % (time.time() - started),
                continue_partial_line=True,
            )
            if blankline_after:
                self.blankline()

    def emit(self, record: logging.LogRecord) -> None:
        blanklines = False
        if record.name.startswith("critic."):
            message = self.system_formatter.format(record)
        elif record.levelno == logging.DEBUG:
            message = self.debug_formatter.format(record)
        elif record.levelno == logging.INFO:
            message = self.info_formatter.format(record)
        else:
            message = self.other_formatter.format(record)
            blanklines = True
        blanklines = getattr(record, "critic.blanklines", blanklines)
        if getattr(record, "critic.type", None) == "header":
            self.blankline()
            message = "%s\n%s\n\n" % (message, "=" * len(message))
        else:
            message = message.rstrip() + "\n"
        if blanklines:
            self.blankline()
        self.output(message)
        if blanklines:
            self.blankline()


@contextlib.contextmanager
def activity(what: str, blanklines: bool = False) -> Iterator[None]:
    OutputManager.instance.start_activity(what, blankline_before=blanklines)
    silent = True
    try:
        yield
        silent = False
    finally:
        OutputManager.instance.end_activity(
            what, blankline_after=blanklines, silent=silent
        )
