from __future__ import annotations

import functools
import json
import logging
import re
import snapshottest
from collections import defaultdict
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    SupportsInt,
    Tuple,
    TypeVar,
    Union,
    runtime_checkable,
)

logger = logging.getLogger(__name__)

from . import Snapshot

T = TypeVar("T", covariant=True)


class Masked:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Masked)

    def __lt__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return hash(Masked)


class MaskedFormatter(snapshottest.formatters.BaseFormatter):
    def can_format(self, value: object) -> bool:
        return isinstance(value, Masked)

    def format(self, anonymous: Masked, indent: Any, formatter: Any) -> Any:
        formatter.imports["tests.utilities"].update(["Masked"])
        return "Masked()"


snapshottest.formatter.Formatter.register_formatter(MaskedFormatter())


class Variable:
    def __init__(self, value: int):
        self.value = value

    def __int__(self) -> int:
        return self.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Variable) and int(self) == int(other)

    def __lt__(self, other: object) -> bool:
        return isinstance(other, Variable) and int(self) < int(other)

    def __hash__(self) -> int:
        return hash(self.value)


class Anonymous:
    def __init__(self, **kwargs: Union[Masked, Variable, str]):
        [(self.key, self.value)] = kwargs.items()

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Anonymous)
            and self.key == other.key
            and self.value == other.value
        )

    def __lt__(self, other: object) -> bool:
        return isinstance(other, Anonymous) and (
            self.key < other.key
            or (self.key == other.key and self.value < other.value)  # type: ignore
        )

    def __hash__(self) -> int:
        return hash((self.key, self.value))

    def __repr__(self) -> str:
        if isinstance(self.value, Masked):
            value = f"Masked()"
        elif isinstance(self.value, Variable):
            value = f"Variable({int(self.value)})"
        else:
            value = repr(self.value)
        return f"Anonymous({self.key}={value})"


class AnonymousFormatter(snapshottest.formatters.BaseFormatter):
    def can_format(self, value: object) -> bool:
        return isinstance(value, Anonymous)

    def format(self, anonymous: Anonymous, indent: Any, formatter: Any) -> Any:
        formatter.imports["tests.utilities"].update(["Anonymous", "Masked", "Variable"])
        return repr(anonymous)


snapshottest.formatter.Formatter.register_formatter(AnonymousFormatter())


def freeze(value: object) -> object:
    if isinstance(value, list):
        return tuple(freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple((key, freeze(item)) for key, item in value.items())
    return value


class Frozen:
    def __init__(self, value: dict):
        self.value = value
        self.frozen = freeze(value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Frozen) and self.frozen == other.frozen

    def __lt__(self, other: object) -> bool:
        return isinstance(other, Frozen) and self.frozen < other.frozen  # type: ignore

    def __hash__(self) -> int:
        return hash(self.frozen)

    def __repr__(self) -> str:
        return f"Frozen({self.value!r})"


class FrozenFormatter(snapshottest.formatters.BaseFormatter):
    def can_format(self, value: object) -> bool:
        return isinstance(value, Frozen)

    def format(self, frozen: Frozen, indent: Any, formatter: Any) -> Any:
        formatter.imports["tests.utilities"].update(["Frozen"])
        return f"Frozen({formatter.format(frozen.value, indent)})"


snapshottest.formatter.Formatter.register_formatter(FrozenFormatter())


@runtime_checkable
class ToJSON(Protocol):
    def to_json(self) -> dict:
        ...


class Pattern:
    def __init__(
        self, pattern: str, parts: Sequence[str], regexp: Optional[re.Pattern]
    ):
        self.pattern = pattern
        self.parts = parts[1:]
        self.regexp = regexp

    @staticmethod
    def parse(sources: Union[str, Sequence[str]]) -> Iterable[Pattern]:
        if isinstance(sources, str):
            sources = [sources]
        for source in sources:
            pattern, colon, regexp = source.partition(":")
            parts = re.findall(r"\$|\w+|\[[^\]]+\]|\.\w+", pattern)
            assert parts[0] == "$", (pattern, parts)
            yield Pattern(
                pattern, parts, re.compile(regexp) if regexp else None,
            )


Data = TypeVar("Data", bound=Union[list, dict, ToJSON])


class Anonymizer:
    replace_strings: List[Tuple[str, str]]
    converters: List[Tuple[Pattern, Callable[[Any], Any]]]

    def __init__(self, snapshot: Snapshot, **keyed: Union[str, Sequence[str]]):
        self.snapshot = snapshot
        self.replacement_map: Dict[str, Dict[Any, Union[Variable, str]]] = {
            key: {} for key in keyed
        }
        self.replacement_counter = {key: 1 for key in keyed}
        self.patterns = []
        self.keys = {}
        self.replace_strings = []
        self.converters = []

        for key, sources in keyed.items():
            for pattern in Pattern.parse(sources):
                self.patterns.append((key, pattern))
                self.keys[pattern.pattern] = key

    def find_key(self, pattern: str) -> str:
        return self.keys[pattern]

    def assert_match(
        self, data: Data, label: str = None, **keyed: Union[str, Sequence[str]],
    ) -> Data:
        self.snapshot.assert_match(self(data, **keyed), label)
        return data

    def __call__(
        self,
        data: object,
        masked: Collection[str] = (),
        **keyed: Union[str, Sequence[str]],
    ) -> object:
        def replacer(key: str, value: Any, from_regexp: bool) -> Any:
            if value is None:
                return None
            if from_regexp:
                try:
                    value = int(value)
                except ValueError:
                    pass
            per_key = self.replacement_map[key]
            label: Union[Masked, Variable, str]
            if None in per_key:
                label = Masked()
            elif value in per_key:
                label = per_key[value]
            else:
                per_key[value] = label = Variable(self.replacement_counter[key])
                self.replacement_counter[key] += 1
            anonymous = Anonymous(**{key: label})
            if from_regexp:
                return f"<{anonymous!r}>"
            return anonymous

        def to_json(data: object) -> object:
            if isinstance(data, ToJSON):
                return data.to_json()
            if isinstance(data, list):
                return [to_json(item) for item in data]
            if isinstance(data, dict):
                return {key: to_json(value) for key, value in data.items()}
            return data

        result = to_json(data)

        for pattern, converter in self.converters:
            result = replace(
                pattern, result, lambda value, from_regexp: converter(value)
            )

        for key, pattern in self.patterns:
            result = replace(pattern, result, functools.partial(replacer, key))

        for key, sources in keyed.items():
            for pattern in Pattern.parse(sources):
                result = replace(pattern, result, functools.partial(replacer, key))

        def replacer_masked(value: Any, from_regexp: bool) -> Any:
            if from_regexp:
                return "****"
            return Masked()

        for masked_item in masked:
            [pattern] = Pattern.parse(masked_item)
            result = replace(pattern, result, replacer_masked)

        result = replace_tokens_and_strings(result, self.replace_strings)

        return result

    def lookup(self, **keyed: Any) -> Optional[Union[Variable, str]]:
        for key, value in keyed.items():
            mapped = self.replacement_map.get(key, {}).get(value)
            if isinstance(mapped, str):
                return mapped
        return None

    def define(self, as_string: bool = False, /, **keyed: Dict[str, Any]) -> Anonymizer:
        for key, data in keyed.items():
            for label, value in data.items():
                assert value not in self.replacement_map[key], (
                    key,
                    value,
                    self.replacement_map[key][value],
                )
                self.replacement_map[key][value] = label
                if as_string:
                    self.replace_strings.append((value, f"<{key}={label!r}>"))
        return self

    def convert(
        self, patterns: Sequence[str], converter: Callable[[Any], Any]
    ) -> Anonymizer:
        self.converters.extend(
            (pattern, converter) for pattern in Pattern.parse(patterns)
        )
        return self

    def replace_string(self, value: str, replacement: str) -> None:
        self.replace_strings.append((value, replacement))


class Filter(Protocol):
    def include(self, item: object) -> bool:
        ...


class All:
    def include(self, item: object) -> bool:
        return True


class WithAttribute:
    def __init__(self, path: str, value: object):
        self.path = path
        self.value = value

    def include(self, item: object):
        try:
            return evaluate_path(self.path, item) == self.value
        except KeyError:
            return False


def parse_expr(expr: str) -> Filter:
    if expr == "*":
        return All()
    match = re.match(r"^(\w+(?:\.\w+)*)=(.+)$", expr)
    if match:
        path, value = match.groups()
        return WithAttribute(path, json.loads(value))
    raise Exception("invalid filter expression: %r", expr)


def replace(pattern: Pattern, data: Any, replacer: Callable[[Any, bool], Any],) -> Any:
    def process(
        parts: Sequence[str], data: Any, replacer: Callable[[Any, bool], Any]
    ) -> Any:
        if not parts:
            if pattern.regexp:
                assert isinstance(data, str), data
                return pattern.regexp.sub(
                    lambda match: replacer(match.group(0), True), data
                )
            return replacer(data, False)
        part = parts[0]
        if part[0] == "[" and part[-1] == "]" and isinstance(data, (list, set)):
            result_type: type
            if isinstance(data, set):
                result_type = set
                data = sorted(data)
            else:
                result_type = list
            expr = part[1:-1]
            filter = parse_expr(expr)
            child_parts = parts[1:]
            return result_type(
                [
                    process(child_parts, item, replacer)
                    if filter.include(item)
                    else item
                    for item in data
                ]
            )
        if part[0] == "." and isinstance(data, dict):
            return {
                key: process(parts[1:], value, replacer) if key == part[1:] else value
                for key, value in sorted(data.items())
            }
        if part[0] == "." and isinstance(data, Frozen):
            return Frozen(process(parts, data.value, replacer))
        return data

    return process(pattern.parts, data, replacer)


def replace_tokens_and_strings(data: Any, strings: Sequence[Tuple[str, str]]) -> Any:
    def inner(data: Any) -> Any:
        if isinstance(data, list):
            return [inner(item) for item in data]
        if isinstance(data, set):
            return {inner(item) for item in data}
        if isinstance(data, dict):
            return {key: inner(value) for key, value in sorted(data.items())}
        if isinstance(data, Frozen):
            return Frozen(inner(data.value))
        if isinstance(data, str):
            for string, replacement in strings:
                data = data.replace(string, replacement)
            return re.sub(r"---[0-9a-f]{8}(?!\w)", "-***", data)
        return data

    return inner(data)


def evaluate_path(path: str, value: object) -> object:
    components = path.split(".")
    for name in components:
        if not isinstance(value, dict):
            raise KeyError
        value = value[name]
    return value
