from __future__ import annotations

import datetime
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, List, Mapping, Optional, Protocol, Sequence, Tuple, Union

logger = logging.getLogger(__name__)


class Adaptable(Protocol):
    def __adapt__(self) -> SQLValue:
        ...


SQLAtom = Union[bool, int, float, str, bytes, datetime.datetime, Adaptable]
SQLValue = Optional[Union[SQLAtom, Sequence[SQLAtom]]]

Parameter = Union[SQLValue, Adaptable]
Parameters = Mapping[str, Parameter]
ExecuteArguments = Optional[Union[List[SQLValue], Parameters]]


def adapt(value: Any) -> Any:
    if value is None:
        return None
    __adapt__ = getattr(value, "__adapt__", None)
    if __adapt__:
        return __adapt__()
    if isinstance(value, (tuple, list, set)):
        return [adapt(item) for item in value]
    return value


class StatementFormatter(ABC):
    regexp = re.compile(r"\{(?:([^=}]+)=)?([^:}]+)(?::(\w+))?\}")

    def format(
        self, sql: str, parameters: Parameters, **kwargs: Any
    ) -> Tuple[str, ExecuteArguments]:
        parameters = {key: adapt(value) for key, value in parameters.items()}
        return self.process(sql, parameters, **kwargs)

    def process(
        self, sql: str, parameters: Parameters, **kwargs: Any
    ) -> Tuple[str, ExecuteArguments]:
        execute_args: ExecuteArguments = None

        def repl(match: re.Match) -> str:
            nonlocal execute_args
            expr, parameter_name, mode = match.groups()
            replacement, execute_args = self.replace(
                expr, parameter_name, mode, execute_args, parameters
            )
            return replacement

        return self.regexp.sub(repl, sql), execute_args

    @abstractmethod
    def replace(
        self,
        expr: Optional[str],
        parameter_name: str,
        mode: Optional[str],
        execute_args: ExecuteArguments,
        parameters: Parameters,
    ) -> Tuple[str, ExecuteArguments]:
        ...
