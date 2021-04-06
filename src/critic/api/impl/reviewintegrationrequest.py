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

import logging
from typing import Callable, Tuple, Optional, Sequence


logger = logging.getLogger(__name__)

from critic import api
from critic.api import reviewintegrationrequest as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult

PublicType = public.ReviewIntegrationRequest
ArgumentsType = Tuple[
    int,
    int,
    int,
    int,
    bool,
    Optional[str],
    bool,
    bool,
    bool,
    bool,
    Optional[api.review.IntegrationStrategy],
    Optional[bool],
    Optional[str],
]


class ReviewIntegrationRequest(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__review_id,
            self.__target_branch_id,
            self.__branchupdate_id,
            self.__do_squash,
            self.__squash_message,
            self.__do_autosquash,
            self.__do_integrate,
            self.__squashed,
            self.__autosquashed,
            self.__strategy_used,
            self.__successful,
            self.__error_message,
        ) = args

        self.__integrated = self.strategy_used is not None
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def review(self) -> api.review.Review:
        return await api.review.fetch(self.critic, self.__review_id)

    @property
    async def target_branch(self) -> api.branch.Branch:
        return await api.branch.fetch(self.critic, self.__target_branch_id)

    @property
    async def branchupdate(self) -> api.branchupdate.BranchUpdate:
        return await api.branchupdate.fetch(self.critic, self.__branchupdate_id)

    @property
    def squash_requested(self) -> bool:
        return self.__do_squash

    @property
    def squash_message(self) -> Optional[str]:
        return self.__squash_message

    @property
    def squash_performed(self) -> bool:
        return self.__squashed

    @property
    def autosquash_requested(self) -> bool:
        return self.__do_autosquash

    @property
    def autosquash_performed(self) -> bool:
        return self.__autosquashed

    @property
    def integration_requested(self) -> bool:
        return self.__do_integrate

    @property
    def integration_performed(self) -> bool:
        """True if integration has been performed.

        Note that "performed" here means "attempted", it might have failed."""
        return self.__integrated

    @property
    def strategy_used(self) -> Optional[api.review.IntegrationStrategy]:
        return self.__strategy_used

    @property
    def successful(self) -> Optional[bool]:
        return self.__successful

    @property
    def error_message(self) -> Optional[str]:
        return self.__error_message

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "review",
    "target",
    "branchupdate",
    "do_squash",
    "squash_message",
    "do_autosquash",
    "do_integrate",
    "squashed",
    "autosquashed",
    "strategy_used",
    "successful",
    "error_message",
)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, request_id: int) -> PublicType:
    return await ReviewIntegrationRequest.ensureOne(
        request_id, queries.idFetcher(critic, ReviewIntegrationRequest)
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review],
    target_branch: Optional[api.branch.Branch],
    performed: Optional[bool],
    successful: Optional[bool],
) -> Sequence[PublicType]:
    conditions = []
    if review is not None:
        conditions.append("review={review}")
    if target_branch is not None:
        conditions.append("target={target_branch}")
    if performed is not None:
        what = "NOT NULL" if performed else "NULL"
        conditions.append(f"strategy_used IS {what}")
    if successful is not None:
        conditions.append("successful={successful}")
    return ReviewIntegrationRequest.store(
        await queries.query(
            critic,
            *conditions,
            review=review,
            target_branch=target_branch,
            performed=performed,
            successful=successful,
        ).make(ReviewIntegrationRequest)
    )
