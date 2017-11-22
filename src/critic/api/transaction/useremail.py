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
from typing import Union

logger = logging.getLogger(__name__)

from . import Transaction, Delete, Insert, LazyAPIObject, Modifier, protocol
from .user import CreatedUser, CreatedUserObject
from critic import api


class CreatedUserEmail(CreatedUserObject, api_module=api.useremail):
    async def create_payload(
        self, resource_name: str, useremail: api.useremail.UserEmail, /
    ) -> protocol.CreatedAPIObject:
        user_id = (await useremail.user).id
        assert user_id is not None, "expected regular user"
        return protocol.CreatedUserEmail(resource_name, useremail.id, user_id)

    @staticmethod
    def make(
        transaction: Transaction,
        user: Union[api.user.User, CreatedUser],
        address: str,
        status: api.useremail.Status,
    ) -> CreatedUserEmail:
        return CreatedUserEmail(transaction, user).insert(
            uid=user, email=address, status=status,
        )


class ModifyUserEmail(Modifier[api.useremail.UserEmail, CreatedUserEmail]):
    def delete(self) -> None:
        self.transaction.items.append(Delete(self.real))

    @staticmethod
    def create(
        transaction: Transaction,
        user: Union[api.user.User, CreatedUser],
        address: str,
        status: api.useremail.Status,
    ) -> ModifyUserEmail:
        return ModifyUserEmail(
            transaction, CreatedUserEmail.make(transaction, user, address, status)
        )
