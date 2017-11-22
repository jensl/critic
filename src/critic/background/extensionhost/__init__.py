from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Sequence, Tuple, Union


from critic import api
from critic import pubsub
from critic import data


@dataclass
class EndpointRequest:
    request_id: bytes
    method: Literal["DELETE", "GET", "PATCH", "POST", "PUT"]
    path: str
    query: List[Tuple[str, str]]
    headers: List[Tuple[str, str]]
    body: Optional[Union[bytes, str]]


@dataclass
class EndpointResponseItem:
    request_id: bytes


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
    request_id: bytes
    channel: pubsub.ChannelName
    payload: pubsub.Payload


@dataclass
class SubscriptionResponseItem:
    request_id: bytes
    error: Optional[str] = None


@dataclass
class SubscriptionRole:
    message: SubscriptionMessage


Role = Union[EndpointRole, SubscriptionRole]


@dataclass
class CallRequest:
    version_id: int
    user_id: Union[Literal["anonymous", "system"], int]
    accesstoken_id: Optional[int]
    role: Role


CallResponseItem = Union[EndpointResponseItem, SubscriptionResponseItem]


@dataclass
class CallResponse:
    success: bool
    items: Sequence[CallResponseItem]


@dataclass
class CallError:
    message: str
    details: Optional[str] = None
    traceback: Optional[str] = None


@dataclass
class CommandPackage:
    token: bytes
    user_id: Union[Literal["anonymous", "system"], int]
    accesstoken_id: Optional[int]
    command: Union[EndpointRequest, SubscriptionMessage]


@dataclass
class ResponsePackage:
    token: bytes


@dataclass
class ResponseItemPackage(ResponsePackage):
    response_item: CallResponseItem


@dataclass
class ResponseErrorPackage(ResponsePackage):
    error: CallError


@dataclass
class ResponseFinalPackage(ResponsePackage):
    pass
