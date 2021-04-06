from typing import Any, Generator, Iterable, List, Optional, Sequence, Set, Tuple

from critic import api
from .extractcontent import extract_context
from .parthelper import PartHelper
from .parts import Parts
from .types import Line, MacroChunk, Part


def getLineContent(
    line_type: api.filediff.LineType,
    old_content: Optional[Sequence[Tuple[Any, ...]]],
    new_content: Optional[Sequence[Tuple[Any, ...]]],
    edits: Optional[str],
) -> Sequence[Part]:
    if line_type == api.filediff.LINE_TYPE_CONTEXT:
        return list(PartHelper.make(old_content))
    else:
        old_parts = PartHelper.make(old_content)
        new_parts = PartHelper.make(new_content)
        if edits:
            return perform_detailed_operations(edits, old_parts, new_parts)
        else:
            return perform_basic_operations(line_type, old_parts, new_parts)


class MacroChunkCreator:
    def __init__(
        self,
        old_offset: int,
        old_count: int,
        old_not_context: Set[int],
        new_offset: int,
        new_count: int,
        new_not_context: Set[int],
        mapped_lines: List[Tuple[int, int, str]],
    ):
        self.old_offset = old_offset
        self.old_count = old_count
        self.old_not_context = old_not_context
        self.old_end = old_offset + old_count
        self.new_offset = new_offset
        self.new_count = new_count
        self.new_not_context = new_not_context
        self.new_end = new_offset + new_count
        self.mapped_lines = mapped_lines

        # FIXME: Typing here.
        self.old_range: Optional[Any] = None
        self.new_range: Optional[Any] = None

    # def __eq__(self, other):
    #     return (
    #         self.old_offset == other.old_offset
    #         and self.old_count == other.old_count
    #         and self.new_offset == other.new_offset
    #         and self.new_count == other.new_count
    #         and self.mapped_lines == other.mapped_lines
    #     )

    # def __repr__(self):
    #     return "MacroChunk(%d, %d, %r, %d, %d, %r, %r)" % (
    #         self.old_offset,
    #         self.old_count,
    #         self.old_range,
    #         self.new_offset,
    #         self.new_count,
    #         self.new_range,
    #         self.mapped_lines,
    #     )

    def getLines(self) -> List[api.filediff.Line]:
        old_offset = self.old_offset
        old_count = self.old_count
        new_offset = self.new_offset
        new_count = self.new_count

        def make_line(
            line_type: Optional[api.filediff.LineType] = None,
            /,
            *,
            edits: Optional[str] = None,
        ) -> api.filediff.Line:
            nonlocal old_offset, old_count, new_offset, new_count
            line_old_offset = old_offset
            line_new_offset = new_offset
            if line_type != api.filediff.LINE_TYPE_INSERTED:
                assert self.old_range
                old_content = self.old_range.lines[old_offset - self.old_offset]
                old_offset += 1
                old_count -= 1
            else:
                old_content = None
            if line_type != api.filediff.LINE_TYPE_DELETED:
                assert self.new_range
                new_content = self.new_range.lines[new_offset - self.new_offset]
                new_offset += 1
                new_count -= 1
            else:
                new_content = None
            if line_type is None:
                if old_content == new_content:
                    line_type = api.filediff.LINE_TYPE_CONTEXT
                elif edits:
                    if edits.startswith("ws"):
                        line_type = api.filediff.LINE_TYPE_WHITESPACE
                        edits = edits[2:].lstrip(",")
                    else:
                        line_type = api.filediff.LINE_TYPE_MODIFIED
                else:
                    line_type = api.filediff.LINE_TYPE_REPLACED
            return Line(
                line_type,
                api.filediff.LINE_TYPE_STRINGS[line_type],
                line_old_offset,
                line_new_offset,
                getLineContent(line_type, old_content, new_content, edits),
            )

        def make_lines() -> Generator[api.filediff.Line, Any, Any]:
            map_offset = 0
            map_old_offset = map_new_offset = edits = None

            def update_mapping() -> None:
                nonlocal map_offset, map_old_offset, map_new_offset, edits
                if map_offset < len(self.mapped_lines):
                    map_old_offset, map_new_offset, edits = self.mapped_lines[
                        map_offset
                    ]
                    if old_offset == map_old_offset and new_offset == map_new_offset:
                        map_offset += 1
                else:
                    map_old_offset = map_new_offset = edits = None

            while old_count or new_count:
                update_mapping()

                if not old_count:
                    yield make_line(api.filediff.LINE_TYPE_INSERTED)
                elif not new_count:
                    yield make_line(api.filediff.LINE_TYPE_DELETED)
                else:
                    if (
                        old_offset not in self.old_not_context
                        and new_offset not in self.new_not_context
                    ):
                        # Neither side is marked as not context, i.e., they are
                        # both context.
                        yield make_line(api.filediff.LINE_TYPE_CONTEXT)
                    elif old_offset == map_old_offset:
                        if new_offset == map_new_offset:
                            yield make_line(edits=edits)
                        else:
                            yield make_line(api.filediff.LINE_TYPE_INSERTED)
                    elif new_offset == map_new_offset:
                        yield make_line(api.filediff.LINE_TYPE_DELETED)
                    elif (
                        old_offset in self.old_not_context
                        and new_offset in self.new_not_context
                    ):
                        yield make_line(api.filediff.LINE_TYPE_REPLACED)
                    elif old_offset in self.old_not_context:
                        yield make_line(api.filediff.LINE_TYPE_DELETED)
                    elif new_offset in self.new_not_context:
                        yield make_line(api.filediff.LINE_TYPE_INSERTED)
                    else:
                        yield make_line()

        return list(make_lines())

    def create(self) -> api.filediff.MacroChunk:
        return MacroChunk(
            self.old_offset,
            self.new_offset,
            self.old_count,
            self.new_count,
            self.getLines(),
        )


def perform_detailed_operations(
    operations: str, old_content: Iterable[Part], new_content: Iterable[Part]
) -> Sequence[Part]:
    processed_content: List[Part] = []

    old_content = list(old_content)
    new_content = list(new_content)

    old_parts = Parts(old_content)
    new_parts = Parts(new_content)

    old_range: Optional[str]
    new_range: Optional[str]

    for operation in operations.split(","):
        if operation[0] == "r":
            old_range, _, new_range = operation[1:].partition("=")
        elif operation[0] == "d":
            old_range = operation[1:]
            new_range = None
        else:
            old_range = None
            new_range = operation[1:]

        if old_range:
            old_begin, old_end = list(map(int, old_range.split("-")))

            context_length = old_begin - old_parts.offset
            if context_length:
                processed_content.extend(
                    extract_context(old_parts, new_parts, context_length)
                )

            deleted_length = old_end - old_begin
            processed_content.extend(
                PartHelper.with_state(part, api.filediff.PART_STATE_DELETED)
                for part in old_parts.extract(deleted_length)
            )

        if new_range:
            new_begin, new_end = list(map(int, new_range.split("-")))

            if not old_range:
                context_length = new_begin - new_parts.offset
                if context_length:
                    processed_content.extend(
                        extract_context(old_parts, new_parts, context_length)
                    )

            inserted_length = new_end - new_begin
            processed_content.extend(
                PartHelper.with_state(part, api.filediff.PART_STATE_INSERTED)
                for part in new_parts.extract(inserted_length)
            )

    assert len(old_parts) == len(new_parts), repr(
        (operations, old_content, new_content)
    )
    processed_content.extend(extract_context(old_parts, new_parts, len(old_parts)))

    return processed_content


def perform_basic_operations(
    line_type: api.filediff.LineType,
    old_content: Iterable[Part],
    new_content: Iterable[Part],
) -> Sequence[Part]:
    if old_content is not None and new_content is not None:
        return [
            PartHelper.with_state(part, api.filediff.PART_STATE_DELETED)
            for part in old_content
        ] + [
            PartHelper.with_state(part, api.filediff.PART_STATE_INSERTED)
            for part in new_content
        ]
    elif old_content is not None:
        return list(old_content)
    assert new_content
    return list(new_content)
