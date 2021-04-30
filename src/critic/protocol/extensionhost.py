from __future__ import annotations

from dataclasses import dataclass, field
import secrets
from typing import List, Literal, Optional, Sequence, Tuple, Union
import traceback

from critic import pubsub


@dataclass
class EndpointRequest:
    method: Literal["DELETE", "GET", "PATCH", "POST", "PUT"]
    path: str
    query: List[Tuple[str, str]]
    headers: List[Tuple[str, str]]
    body: Optional[Union[bytes, str]]


@dataclass
class ResponseItem:
    error: Optional[CallError]


@dataclass
class EndpointResponseItem(ResponseItem):
    pass


@dataclass
class EndpointResponsePrologue(EndpointResponseItem):
    status_code: int
    status_text: str
    headers: List[Tuple[str, str]]


@dataclass
class EndpointResponseBodyFragment(EndpointResponseItem):
    data: bytes


@dataclass
class EndpointResponseEnd(EndpointResponseItem):
    failed: bool = False


@dataclass
class EndpointRole:
    name: str
    request: EndpointRequest


@dataclass
class SubscriptionMessage:
    channel: pubsub.ChannelName
    payload: pubsub.Payload


@dataclass
class SubscriptionResponseItem(ResponseItem):
    pass


@dataclass
class SubscriptionRole:
    message: SubscriptionMessage


Role = Union[EndpointRole, SubscriptionRole]


def generate_request_id() -> int:
    return int.from_bytes(secrets.token_bytes(8), "big", signed=True)


@dataclass
class CallRequest:
    version_id: int
    user_id: Union[Literal["anonymous", "system"], int]
    accesstoken_id: Optional[int]
    role: Role

    request_id: int = field(default_factory=generate_request_id, repr=False)


@dataclass
class CallError:
    message: str
    details: Optional[str] = None
    traceback: Optional[str] = None

    @staticmethod
    def from_exception(error: BaseException) -> CallError:
        return CallError(str(error), None, traceback.format_exc())


CallResponseItem = Union[ResponseItem, CallError]


@dataclass
class CallLogRecord:
    level: int
    name: str
    message: str


@dataclass
class CallResponse:
    success: bool
    items: Sequence[CallResponseItem]
    log: Sequence[CallLogRecord]


@dataclass
class CommandPackage:
    token: str
    user_id: Union[Literal["anonymous", "system"], int]
    accesstoken_id: Optional[int]
    command: Union[EndpointRequest, SubscriptionMessage]


@dataclass
class ResponsePackage:
    token: str


@dataclass
class ResponseItemPackage(ResponsePackage):
    response_item: CallResponseItem


@dataclass
class ResponseErrorPackage(ResponsePackage):
    error: CallError


@dataclass
class ResponseFinalPackage(ResponsePackage):
    pass
