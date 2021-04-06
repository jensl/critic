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
from critic import dbaccess
from ..base import TransactionBase, Finalizer


class ClearWouldBeAcceptedTag(Finalizer):
    tables = frozenset(("reviewusertags",))

    def __init__(self, review: api.review.Review):
        self.__review = review
        self.__user = review.critic.effective_user
        super().__init__(self.__review, self.__user)

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor
    ) -> None:
        would_be_accepted = await api.reviewtag.fetch(
            transaction.critic, name="would_be_accepted"
        )
        would_be_unaccepted = await api.reviewtag.fetch(
            transaction.critic, name="would_be_unaccepted"
        )
        await cursor.delete(
            "reviewusertags",
            review=self.__review,
            uid=self.__user,
            tag=[would_be_accepted, would_be_unaccepted],
        )
