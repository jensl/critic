# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import Any, Iterable, Optional

from critic.base.types import BooleanWithReason

logger = logging.getLogger(__name__)

from critic import api


class APIError(Exception):
    """Base exception for all errors caused by incorrect API usage (including
    invalid input.)"""

    object_type: Optional[str] = None

    def __init_subclass__(cls, object_type: Optional[str] = None) -> None:
        if object_type is not None:
            cls.object_type = object_type

    def __init__(self, message: str, *, code: Optional[str] = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code

    @classmethod
    def getModule(cls) -> ModuleType:
        """Return the module object that implements this API object type.

        This can be used to access other predictably named items from the
        module, such as the `Error` class and the `fetch()` function, in a
        generic fashion."""
        return importlib.import_module(cls.__module__)

    @classmethod
    def raiseIf(cls, condition: BooleanWithReason) -> None:
        if condition:
            raise cls(condition.reason)

    @classmethod
    def raiseUnless(cls, condition: BooleanWithReason) -> None:
        if not condition:
            raise cls(condition.reason)


class InvalidItemError(APIError):
    item_type: Optional[str] = None

    def __init_subclass__(cls, *, item_type: Optional[str] = None) -> None:
        if item_type is not None:
            cls.item_type = item_type

    def __init__(self, *, value: Any, **kwargs: Any) -> None:
        super().__init__(
            f"Invalid {self.object_type} {self.item_type} used: {value}", **kwargs
        )
        self.value = value


class InvalidItemsError(APIError):
    items_type: Optional[str] = None

    def __init_subclass__(cls, *, items_type: Optional[str] = None):
        if items_type is not None:
            cls.items_type = items_type

    def __init__(self, *, values: Iterable[Any], **kwargs: Any) -> None:
        super().__init__(
            f"Invalid {self.object_type} {self.items_type} used: "
            f"{', '.join(str(value) for value in values)}",
            **kwargs,
        )
        self.values = list(values)


class InvalidIdError(InvalidItemError, item_type="id"):
    code = "INVALID_ID"

    def __init__(self, *args: Any, invalid_id: Any, **kwargs: Any) -> None:
        super().__init__(*args, value=invalid_id, **kwargs)


class InvalidIdsError(InvalidItemsError, items_type="ids"):
    code = "INVALID_IDS"

    def __init__(self, *args: Any, invalid_ids: Iterable[Any], **kwargs: Any) -> None:
        super().__init__(*args, values=invalid_ids, **kwargs)


class PermissionDenied(Exception):
    """Exception raised on correct API usage that the current user is not
    allowed."""

    @staticmethod
    def raiseUnlessAdministrator(critic: api.critic.Critic) -> None:
        if critic.session_type == "system":
            return
        if not (critic.actual_user and critic.actual_user.hasRole("administrator")):
            raise PermissionDenied("Must be an administrator")

    @staticmethod
    def raiseIfRegularUser(critic: api.critic.Critic) -> None:
        if critic.session_type == "user":
            PermissionDenied.raiseUnlessAdministrator(critic)

    @staticmethod
    def raiseUnlessUser(
        critic: api.critic.Critic, required_user: Optional[api.user.User]
    ) -> None:
        if critic.session_type == "system":
            return
        if not (critic.actual_user and critic.actual_user == required_user):
            PermissionDenied.raiseUnlessAdministrator(critic)

    @staticmethod
    def raiseUnlessSystem(critic: api.critic.Critic) -> None:
        if critic.session_type != "system":
            PermissionDenied.raiseUnlessAdministrator(critic)

    @staticmethod
    def raiseUnlessService(*service_names: str) -> None:
        from critic import background

        for service_name in service_names:
            if background.utils.is_background_service(service_name):
                return
        raise PermissionDenied(
            "Reserved for use in %s service(s)" % ", ".join(sorted(service_names))
        )


class TransactionError(APIError):
    """Base exception for transaction errors."""

    pass


class ResultDelayedError(Exception):
    """Base exception for all errors caused by the result being temporarily
    unavailable"""

    pass


class DatabaseSchemaError(Exception):
    """Exception raised when some part of the API is non-functional due to
    database schema problems"""

    pass
