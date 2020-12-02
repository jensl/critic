from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

from .types import Parameters, ExecuteArguments, adapt


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
        execute_args: Optional[ExecuteArguments] = None

        def repl(match: re.Match[str]) -> str:
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
