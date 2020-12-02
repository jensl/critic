from contextlib import contextmanager
import os
from os import environ
from pathlib import Path
from typing import Dict, Iterator, Optional, TypeVar


T = TypeVar("T")


def asserted(value: Optional[T]) -> T:
    assert value is not None
    return value


@contextmanager
def environment(**values: str) -> Iterator[None]:
    previous: Dict[str, Optional[str]] = {
        name: os.getenv(name) for name in values.keys()
    }

    for name, value in values.items():
        os.putenv(name, value)

    try:
        yield None
    finally:
        for name, previous_value in previous.items():
            if previous_value is None:
                os.unsetenv(name)
            else:
                os.putenv(name, previous_value)


@contextmanager
def git_askpass() -> Iterator[None]:
    path = Path(__file__).parent / "scripts/git-askpass"
    with environment(GIT_ASKPASS=str(path)):
        yield None
