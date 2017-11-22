from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class RequestBase:
    secret: str


@dataclass
class ForwardRequest(RequestBase):
    service_name: str


@dataclass
class WakeUpRequest(RequestBase):
    service_name: str


@dataclass
class Response:
    status: Literal["ok", "error"]
    message: Optional[str] = None
