# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

import logging
from typing import Tuple, Union

logger = logging.getLogger(__name__)

from .. import LazyAPIObject, Transaction
from critic import api


class CreatedUser(LazyAPIObject, api_module=api.user):
    pass


class CreatedUserObject(LazyAPIObject):
    def __init__(
        self, transaction: Transaction, user: Union[api.user.User, CreatedUser]
    ) -> None:
        if isinstance(user, api.user.User):
            api.PermissionDenied.raiseUnlessUser(transaction.critic, user)
        else:
            api.PermissionDenied.raiseUnlessAdministrator(transaction.critic)
        super().__init__(transaction)
        self.user = user

    def scopes(self) -> LazyAPIObject.Scopes:
        return (f"users/{int(self.user)}",)


from .create import create_user
from .modify import ModifyUser

__all__ = ["create_user", "ModifyUser"]
