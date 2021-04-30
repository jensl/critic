# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

from typing import Any, Optional

from critic import api
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject
from . import valueAsJSON


class CreatedSetting(CreateAPIObject[api.setting.Setting], api_module=api.setting):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        scope: str,
        name: str,
        value: Any,
        value_bytes: Optional[bytes],
        user: Optional[api.user.User],
        repository: Optional[api.repository.Repository],
        branch: Optional[api.branch.Branch],
        review: Optional[api.review.Review],
        extension: Optional[api.extension.Extension],
    ) -> api.setting.Setting:
        critic = transaction.critic

        if user:
            api.PermissionDenied.raiseUnlessUser(transaction.critic, user)
        else:
            api.PermissionDenied.raiseUnlessAdministrator(transaction.critic)

        try:
            await api.setting.fetch(
                critic,
                scope=scope,
                name=name,
                user=user,
                repository=repository,
                branch=branch,
                review=review,
                extension=extension,
            )
        except api.setting.NotDefined:
            pass
        else:
            raise api.setting.Error("Setting already defined: %s:%s" % (scope, name))

        return await CreatedSetting(transaction).insert(
            scope=scope,
            name=name,
            value=valueAsJSON(value),
            value_bytes=value_bytes,
            user=user,
            repository=repository,
            branch=branch,
            review=review,
            extension=extension,
        )
