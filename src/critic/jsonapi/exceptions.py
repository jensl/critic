from __future__ import annotations

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

from critic import api


class Error(Exception):
    http_status: int
    title: str
    code: Optional[str] = None

    def as_json(self) -> dict:
        return {
            "error": {
                "title": self.title,
                "message": str(self.args[0]),
                "code": self.code,
            }
        }


class PathError(Error):
    """Raised for valid paths that don't match a resource

       Results in a 404 "Not Found" response.

       Note: A "valid" path is one that could have returned a resource, had the
             system's dynamic state (database + repositories) been different."""

    http_status = 404
    title = "No such resource"

    def __init__(self, message: str, *, code: str = None, error: BaseException = None):
        super().__init__(message)
        self.code = code
        self.error = error

    def as_json(self) -> dict:
        result = super().as_json()
        if isinstance(self.error, api.InvalidIdError):
            result["invalid"] = {
                getattr(self.error.getModule(), "resource_name"): [self.error.value]
            }
        return result


class UsageError(Error):
    """Raised for invalid paths and/or query parameters

       Results in a 400 "Bad Request" response.

       Note: An "invalid" path is one that could never (in this version of
             Critic) return any other response, regardless of the system's
             dynamic state (database + repositories.)"""

    http_status = 400
    title = "Invalid API request"

    def __init__(self, message: str, *, code: str = None, error: BaseException = None):
        if code is not None:
            self.code = code
        elif isinstance(error, api.APIError) and hasattr(error, "code"):
            logger.error("APIError: %s", error.code)
            self.code = error.code
        else:
            self.code = None
        super().__init__(message)

    @staticmethod
    def invalidParameter(
        name: str, value: Any = None, *, expected: str = None, message: str = None
    ) -> UsageError:
        text = f"Invalid {name} parameter"
        if value is not None:
            text += f": {value!r}"
        if expected is not None:
            text += f"; expected {expected}"
        if message is not None:
            text += f"; {message}"
        return UsageError(text)

    @staticmethod
    def missingParameter(name: str) -> UsageError:
        return UsageError(f"Missing parameter: '{name}'")

    @staticmethod
    def redundantParameter(name: str, *, reason: str = None) -> UsageError:
        text = f"Redundant parameter: '{name}'"
        if reason:
            text += f" ({reason})"
        return UsageError(text)

    @staticmethod
    def invalidInput(
        data: dict, name: str, *, expected: str = None, details: str = None
    ) -> UsageError:
        message = f"Invalid {name} input: {data[name]!r}"
        if expected is not None:
            message += f"; expected {expected}"
        if details is not None:
            message += f": {details}"
        return UsageError(message)

    @staticmethod
    def missingInput(name: str) -> UsageError:
        return UsageError(f"Missing input: '{name}'")


class InputError(Error):
    http_status = 400
    title = "Invalid API input"


class PermissionDenied(Error):
    http_status = 403
    title = "Permission denied"


class ResultDelayed(Error):
    http_status = 202
    title = "Resource temporarily unavailable"


class ResourceSkipped(Exception):
    """Raised by a resource class's json() to skip the resource

       The message should explain why it was skipped, which may be
       sent to the client in a "404 Not Found" response."""

    pass
