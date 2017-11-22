from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Sequence, Mapping, NewType, Union

from critic.gitaccess import (
    FetchRangeOrder,
    GitError,
    GitRawObject,
    ObjectType,
    SHA1,
    StreamCommand,
)


RequestId = NewType("RequestId", int)


@dataclass
class RequestBase:
    request_id: RequestId
    repository_path: str


@dataclass
class FetchRequest(RequestBase):
    object_ids: Sequence[SHA1]

    def response(self, object_id: SHA1, raw_object: GitRawObject) -> FetchObject:
        return FetchObject(
            self.request_id,
            raw_object.sha1,
            raw_object.object_type,
            raw_object.data,
            object_id,
        )

    def error(
        self, exception: GitError, stacktrace: str = "", object_id: SHA1 = None
    ) -> FetchError:
        return FetchError(self.request_id, exception, stacktrace, object_id)


@dataclass
class FetchRangeRequest(RequestBase):
    include: Sequence[str]
    exclude: Sequence[str]
    order: Optional[FetchRangeOrder]
    skip: Optional[int]
    limit: Optional[int]

    def response_object(self, raw_object: GitRawObject) -> FetchRangeObject:
        return FetchRangeObject(
            self.request_id, raw_object.sha1, raw_object.object_type, raw_object.data
        )

    def response_end(self) -> FetchRangeEnd:
        return FetchRangeEnd(self.request_id)

    def error(self, exception: GitError, stacktrace: str = "") -> FetchRangeError:
        return FetchRangeError(self.request_id, exception, stacktrace)


Call = Literal[
    "version",
    "repositories_dir",
    "symbolicref",
    "revlist",
    "revparse",
    "mergebase",
    "lstree",
    "foreachref",
    "updateref",
    "lsremote",
]


@dataclass
class CallRequest(RequestBase):
    call: Call
    args: Sequence[Any]
    kwargs: Mapping[str, Any]

    def response(self, result: Any) -> CallResult:
        return CallResult(self.request_id, result)

    def error(self, exception: GitError, stacktrace: str = "") -> CallError:
        return CallError(self.request_id, exception, stacktrace)


@dataclass
class StreamRequest(RequestBase):
    command: StreamCommand
    env: Mapping[str, str]

    def response_output(self, data: bytes) -> StreamOutput:
        return StreamOutput(self.request_id, data)

    def response_end(self) -> StreamEnd:
        return StreamEnd(self.request_id)

    def error(self, exception: GitError, stacktrace: str = "") -> StreamError:
        return StreamError(self.request_id, exception, stacktrace)


@dataclass
class StreamInput:
    request_id: RequestId
    data: bytes


InputMessage = Union[
    FetchRequest, FetchRangeRequest, CallRequest, StreamRequest, StreamInput
]


@dataclass
class ResponseBase:
    request_id: RequestId


@dataclass
class ErrorResponse:
    exception: GitError
    stacktrace: str = ""


@dataclass
class GitObject:
    sha1: SHA1
    object_type: ObjectType
    data: bytes


@dataclass
class FetchObject(GitObject, ResponseBase):
    object_id: SHA1


@dataclass
class FetchError(ErrorResponse, ResponseBase):
    object_id: Optional[SHA1] = None


FetchResponse = Union[FetchObject, FetchError]


@dataclass
class FetchRangeObject(GitObject, ResponseBase):
    pass


@dataclass
class FetchRangeEnd(ResponseBase):
    pass


@dataclass
class FetchRangeError(ErrorResponse, ResponseBase):
    pass


FetchRangeResponse = Union[FetchRangeObject, FetchRangeEnd, FetchRangeError]


@dataclass
class CallResult(ResponseBase):
    result: Any


@dataclass
class CallError(ErrorResponse, ResponseBase):
    pass


CallResponse = Union[CallResult, CallError]


@dataclass
class StreamOutput:
    request_id: RequestId
    data: bytes


@dataclass
class StreamEnd(ResponseBase):
    pass


@dataclass
class StreamError(ErrorResponse, ResponseBase):
    pass


StreamResponse = Union[StreamOutput, StreamEnd, StreamError]

OutputMessage = Union[
    FetchResponse, FetchRangeResponse, CallResponse, StreamResponse, StreamOutput
]
