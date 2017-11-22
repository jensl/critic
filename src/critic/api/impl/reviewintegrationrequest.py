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
from typing import Tuple, Optional, Sequence

logger = logging.getLogger(__name__)

from . import apiobject

from critic import api

WrapperType = api.reviewintegrationrequest.ReviewIntegrationRequest
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
    Optional[str],
    Optional[bool],
    Optional[str],
]


class ReviewIntegrationRequest(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    column_names = [
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
    ]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.__review_id,
            self.__target_branch_id,
            self.__branchupdate_id,
            self.do_squash,
            self.squash_message,
            self.do_autosquash,
            self.do_integrate,
            self.squashed,
            self.autosquashed,
            self.strategy_used,
            self.successful,
            self.error_message,
        ) = args

        self.integrated = self.strategy_used is not None

    async def getReview(self, critic: api.critic.Critic) -> api.review.Review:
        return await api.review.fetch(critic, self.__review_id)

    async def getTargetBranch(self, critic: api.critic.Critic) -> api.branch.Branch:
        return await api.branch.fetch(critic, self.__target_branch_id)

    async def getBranchUpdate(
        self, critic: api.critic.Critic
    ) -> api.branchupdate.BranchUpdate:
        return await api.branchupdate.fetch(critic, self.__branchupdate_id)


@ReviewIntegrationRequest.cached
async def fetch(critic: api.critic.Critic, request_id: int) -> WrapperType:
    async with critic.query(
        f"""SELECT {ReviewIntegrationRequest.columns()}
              FROM {ReviewIntegrationRequest.table()}
             WHERE id={{request_id}}""",
        request_id=request_id,
    ) as result:
        return await ReviewIntegrationRequest.makeOne(critic, result)


async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review],
    target_branch: Optional[api.branch.Branch],
    performed: Optional[bool],
    successful: Optional[bool],
) -> Sequence[WrapperType]:
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
    logger.debug(repr(conditions))
    async with critic.query(
        f"""SELECT {ReviewIntegrationRequest.columns()}
              FROM {ReviewIntegrationRequest.table()}
             WHERE {" AND ".join(conditions)}""",
        review=review,
        target_branch=target_branch,
        performed=performed,
        successful=successful,
    ) as result:
        return await ReviewIntegrationRequest.make(critic, result)
