import asyncio
from importlib import import_module
import logging
import sys

from .arguments import parse as parse_arguments


async def main() -> int:
    arguments = parse_arguments()

    logging.basicConfig(level=arguments.loglevel)

    for recipe in arguments.recipe:
        module = import_module(f".{recipe}", "scenarios.recipies")
        await getattr(module, "main")()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
