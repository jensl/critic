from typing import Any, Generator, Iterable, Optional, Tuple

from critic import api
from .types import Part


class PartHelper:
    @staticmethod
    def with_content(part: Part, content: str) -> Part:
        return Part(content, part.type, part.state)

    @staticmethod
    def with_state(part: Part, state: api.filediff.PartState) -> Part:
        return Part(part.content, part.type, state)

    @staticmethod
    def copy(part: Part) -> Part:
        return Part(part.content, part.type, part.state)

    @staticmethod
    def make(content: Optional[Iterable[Tuple[Any, ...]]]) -> Generator[Part, Any, Any]:
        return (Part(*values) for values in (content or []))
