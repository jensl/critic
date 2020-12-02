import argparse
from contextvars import ContextVar
import logging
import os
from pathlib import Path
import pwd
from typing import Collection, Protocol, Sequence, cast


class Arguments(Protocol):
    loglevel: int

    backend: str
    admin_username: str
    admin_password: str

    recipe: Sequence[str]


_arguments: ContextVar[Arguments] = ContextVar("arguments")


def get() -> Arguments:
    return _arguments.get()


def list_recipies() -> Collection[str]:
    recipies = set()
    recipe_dir = Path(__file__).parent / "recipies"
    for module in recipe_dir.glob("*.py"):
        if module.name == "__init__.py":
            continue
        recipies.add(module.stem)
    return recipies


def parse() -> Arguments:
    parser = argparse.ArgumentParser()

    output = parser.add_argument_group("Output options")
    output.add_argument(
        "--verbose",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        help="Enable debug output.",
    )
    output.add_argument(
        "--quiet",
        action="store_const",
        dest="loglevel",
        const=logging.WARNING,
        help="Disable purely informative output.",
    )

    parser.add_argument("--backend", default="http://localhost:8080")
    parser.add_argument("--admin-username", default=pwd.getpwuid(os.geteuid()).pw_name)
    parser.add_argument("--admin-password", default="1234")

    parser.add_argument(
        "recipe", metavar="RECIPE", nargs="+", choices=sorted(list_recipies())
    )

    parser.set_defaults(loglevel=logging.INFO)

    _arguments.set(cast(Arguments, parser.parse_args()))

    return get()
