import contextlib
import logging
import os
import pwd
import sys
from typing import Callable, Iterator, Optional, NoReturn

logger = logging.getLogger(__name__)

_is_quickstarted: Optional[bool] = None
_is_virtualenv = sys.prefix != sys.base_prefix


def is_quickstarted() -> bool:
    assert _is_quickstarted is not None
    return _is_quickstarted


def set_is_quickstarted(value: bool) -> None:
    global _is_quickstarted
    _is_quickstarted = value


def is_virtualenv() -> bool:
    return _is_virtualenv


@contextlib.contextmanager
def temporary_cwd(cwd: str, use_fallback: bool = True) -> Iterator[None]:
    previous_cwd = os.getcwd()

    try:
        os.chdir(cwd)
    except OSError:
        if not use_fallback:
            raise
        os.chdir("/")

    try:
        yield
    finally:
        os.chdir(previous_cwd)


class InvalidUser(Exception):
    pass


@contextlib.contextmanager
def as_user(
    *, uid: Optional[int] = None, name: Optional[str] = None
) -> Iterator[Callable[[], None]]:
    assert (uid is None) != (name is None)

    if uid is not None:
        pwentry = pwd.getpwuid(uid)
    else:
        assert name is not None
        try:
            pwentry = pwd.getpwnam(name)
        except KeyError:
            raise InvalidUser("%s: no such user" % name) from None

    if uid == os.geteuid() or os.getuid() != 0:
        yield lambda: None
        return

    previous_euid = os.geteuid()

    try:
        os.seteuid(pwentry.pw_uid)
    except OSError as error:
        logger.error("Failed to set effective uid: %s", error)
        sys.exit(1)

    def restore_user():
        nonlocal previous_euid
        if previous_euid is not None:
            os.seteuid(previous_euid)
            previous_euid = None

    with temporary_cwd(pwentry.pw_dir):
        try:
            yield restore_user
        finally:
            restore_user()


@contextlib.contextmanager
def as_root():
    if _is_quickstarted:
        yield
        return

    euid = os.geteuid()
    egid = os.getegid()

    try:
        os.seteuid(0)
        os.setegid(0)
    except OSError as error:
        logger.error("Failed to set effective uid/gid: %s", error)
        sys.exit(1)

    try:
        yield
    finally:
        os.setegid(egid)
        os.seteuid(euid)


def fail(message: str, *additional: str) -> NoReturn:
    from critic import textutils

    def for_each_line(fn: Callable[[str], None], string: str) -> None:
        for line in textutils.reflow(string, line_length=70).splitlines():
            fn(line)

    for_each_line(logger.error, f"{message}")

    if additional:
        for string in additional:
            logger.info("")
            for_each_line(logger.info, string)
        logger.info("")

    sys.exit(1)
