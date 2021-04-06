from typing import Iterable

from critic import api
from .parthelper import PartHelper
from .parts import Parts
from .types import Part


def extract_context(
    old_parts: Parts, new_parts: Parts, context_length: int
) -> Iterable[Part]:
    old_parts_list = list(old_parts.extract(context_length))
    new_parts_list = list(new_parts.extract(context_length))

    if old_parts_list == new_parts_list:
        yield from old_parts_list
        return

    old_parts_iter = iter(old_parts_list)
    new_parts_iter = iter(new_parts_list)

    old_part = next(old_parts_iter, None)
    new_part = next(new_parts_iter, None)
    old_offset = new_offset = 0

    def consume_old_part() -> None:
        nonlocal old_part, old_offset
        part = old_part
        assert part
        old_offset += len(part)
        old_part = next(old_parts_iter, None)

    def emit_old_part() -> Part:
        assert old_part
        part = old_part
        consume_old_part()
        return part

    def consume_new_part() -> None:
        nonlocal new_part, new_offset
        assert new_part
        new_offset += len(new_part)
        new_part = next(new_parts_iter, None)

    def emit_new_part() -> Part:
        assert new_part
        part = new_part
        consume_new_part()
        return part

    while True:
        if old_part is None and new_part is None:
            break

        if old_offset == new_offset and old_part == new_part:
            # Output the old part as "neutral", i.e. unchanged.
            yield emit_old_part()
            # Discard the new part, as it's identical to the old part.
            consume_new_part()
            continue

        if old_offset < new_offset and old_part is not None:
            yield PartHelper.with_state(emit_old_part(), api.filediff.PART_STATE_OLD)
            continue
        if new_offset < old_offset and new_part is not None:
            yield PartHelper.with_state(emit_new_part(), api.filediff.PART_STATE_NEW)
            continue

        if old_part is not None:
            yield PartHelper.with_state(emit_old_part(), api.filediff.PART_STATE_OLD)
        if new_part is not None:
            yield PartHelper.with_state(emit_new_part(), api.filediff.PART_STATE_NEW)
