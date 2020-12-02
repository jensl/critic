from typing import Protocol, Any

from .outputter import Outputter


class Highlighter(Protocol):
    def __call__(self, source: str, outputter: Outputter) -> Any:
        ...
