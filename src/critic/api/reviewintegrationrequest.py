# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2019 the Critic contributors, Opera Software ASA
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

from typing import Optional, Sequence

import logging

logger = logging.getLogger(__name__)

from critic import api


class Error(api.APIError, object_type="review integration request"):
    """Base exception for all errors related to the ReviewIntegrationRequest
       class."""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised by `fetch()` when an invalid integration request id is used."""

    pass


class ReviewIntegrationRequest(api.APIObject):
    @property
    def id(self) -> int:
        return self._impl.id

    @property
    async def review(self) -> api.review.Review:
        return await self._impl.getReview(self.critic)

    @property
    async def target_branch(self) -> api.branch.Branch:
        return await self._impl.getTargetBranch(self.critic)

    @property
    async def branchupdate(self) -> api.branchupdate.BranchUpdate:
        return await self._impl.getBranchUpdate(self.critic)

    @property
    def squash_requested(self) -> bool:
        return self._impl.do_squash

    @property
    def squash_message(self) -> str:
        return self._impl.squash_message

    @property
    def squash_performed(self) -> bool:
        return self._impl.squashed

    @property
    def autosquash_requested(self) -> bool:
        return self._impl.do_autosquash

    @property
    def autosquash_performed(self) -> bool:
        return self._impl.autosquashed

    @property
    def integration_requested(self) -> bool:
        return self._impl.do_integrate

    @property
    def integration_performed(self) -> bool:
        """True if integration has been performed.

        Note that "performed" here means "attempted", it might have failed."""
        return self._impl.integrated

    @property
    def strategy_used(self) -> Optional[api.review.IntegrationStrategy]:
        return self._impl.strategy_used

    @property
    def successful(self) -> Optional[bool]:
        return self._impl.successful

    @property
    def error_message(self) -> Optional[str]:
        return self._impl.error_message


async def fetch(critic: api.critic.Critic, request_id: int) -> ReviewIntegrationRequest:
    from .impl import reviewintegrationrequest as impl

    return await impl.fetch(critic, request_id)


async def fetchAll(
    critic: api.critic.Critic,
    *,
    review: api.review.Review = None,
    target_branch: api.branch.Branch = None,
    performed: bool = None,
    successful: bool = None
) -> Sequence[ReviewIntegrationRequest]:
    from .impl import reviewintegrationrequest as impl

    return await impl.fetchAll(critic, review, target_branch, performed, successful)


resource_name = table_name = "reviewintegrationrequests"
