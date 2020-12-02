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
from ..item import Delete, Update


async def set_status(
    transaction: TransactionBase,
    user: api.user.User,
    new_status: api.user.Status,
) -> None:
    await transaction.execute(Update(user).set(status=new_status))

    if new_status == "disabled":
        await transaction.execute(
            Update(user).set(
                name=f"__disabled_{user.id}__",
                fullname="(disabled account)",
                password=None,
            )
        )

        await transaction.execute(Delete("useremails").where(uid=user))
        await transaction.execute(Delete("usergitemails").where(uid=user))
        await transaction.execute(Delete("userroles").where(uid=user))

    if new_status in ("retired", "disabled"):
        # Delete all assignments that the user hasn't reviewed yet. Assignments that the
        # user has reviewed are left; otherwise the state of existing (potentially
        # finished) reviews will be odd -- changes marked as reviewed but no record of
        # who reviewed them.
        await transaction.execute(
            Delete("reviewuserfiles").where(uid=user, reviewed=False)
        )
