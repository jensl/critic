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

logger = logging.getLogger(__name__)

from critic import api
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject
from ..protocol import CreatedAPIObject, CreatedUserEmail


class CreateUserEmail(
    CreateAPIObject[api.useremail.UserEmail], api_module=api.useremail
):
    async def create_payload(
        self, resource_name: str, useremail: api.useremail.UserEmail, /
    ) -> CreatedAPIObject:
        user_id = (await useremail.user).id
        assert user_id is not None, "expected regular user"
        return CreatedUserEmail(resource_name, useremail.id, user_id)

    @staticmethod
    async def make(
        transaction: TransactionBase,
        user: api.user.User,
        address: str,
        status: api.useremail.Status,
    ) -> api.useremail.UserEmail:
        return await CreateUserEmail(transaction).insert(
            uid=user,
            email=address,
            status=status,
        )
