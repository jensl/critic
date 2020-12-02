from __future__ import annotations

import aiohttp.web
import json
import logging
from typing import Optional, Any, Dict, Type

logger = logging.getLogger(__name__)

from critic import api
from .types import JSONInput


class Error(Exception):
    http_exception_type: Type[aiohttp.web.HTTPException]
    title: str
    code: Optional[str] = None

    def as_json(self) -> Dict[str, Any]:
        return {
            "error": {
                "title": self.title,
                "message": str(self.args[0]),
                "code": self.code,
            }
        }

    @property
    def http_exception(self) -> Exception:
        raise self.http_exception_type(
            content_type="application/json", text=json.dumps(self.as_json())
        )


class PathError(Error):
    """Raised for valid paths that don't match a resource

    Results in a 404 "Not Found" response.

    Note: A "valid" path is one that could have returned a resource, had the
          system's dynamic state (database + repositories) been different."""

    http_exception_type = aiohttp.web.HTTPNotFound
    title = "No such resource"

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        error: Optional[BaseException] = None,
    ):
        super().__init__(message)
        self.code = code
        self.error = error

    def as_json(self) -> Dict[str, Any]:
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

    http_exception_type = aiohttp.web.HTTPBadRequest
    title = "Invalid API request"

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        error: Optional[BaseException] = None,
    ):
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
        name: str,
        value: Optional[Any] = None,
        *,
        expected: Optional[str] = None,
        message: Optional[str] = None,
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
    def redundantParameter(name: str, *, reason: Optional[str] = None) -> UsageError:
        text = f"Redundant parameter: '{name}'"
        if reason:
            text += f" ({reason})"
        return UsageError(text)

    @staticmethod
    def invalidInput(
        data: JSONInput,
        name: str,
        *,
        expected: Optional[str] = None,
        details: Optional[str] = None,
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
    http_exception_type = aiohttp.web.HTTPBadRequest
    title = "Invalid API input"


class PermissionDenied(Error):
    http_exception_type = aiohttp.web.HTTPForbidden
    title = "Permission denied"


class ResultDelayed(Error):
    http_exception_type = aiohttp.web.HTTPAccepted
    title = "Resource temporarily unavailable"


class ResourceSkipped(Exception):
    """Raised by a resource class's json() to skip the resource

    The message should explain why it was skipped, which may be
    sent to the client in a "404 Not Found" response."""

    pass
