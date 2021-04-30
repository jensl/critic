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
from abc import abstractmethod

from typing import Awaitable, Callable, Optional, Sequence

import logging

from critic.api.apiobject import FunctionRef

logger = logging.getLogger(__name__)

from critic import api


class Error(api.APIError, object_type="review integration request"):
    """Base exception for all errors related to the ReviewIntegrationRequest
    class."""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised by `fetch()` when an invalid integration request id is used."""

    pass


class ReviewIntegrationRequest(api.APIObjectWithId):
    @property
    @abstractmethod
    def id(self) -> int:
        ...

    @property
    @abstractmethod
    async def review(self) -> api.review.Review:
        ...

    @property
    @abstractmethod
    async def target_branch(self) -> api.branch.Branch:
        ...

    @property
    @abstractmethod
    async def branchupdate(self) -> api.branchupdate.BranchUpdate:
        ...

    @property
    @abstractmethod
    def squash_requested(self) -> bool:
        ...

    @property
    @abstractmethod
    def squash_message(self) -> Optional[str]:
        ...

    @property
    @abstractmethod
    def squash_performed(self) -> bool:
        ...

    @property
    @abstractmethod
    def autosquash_requested(self) -> bool:
        ...

    @property
    @abstractmethod
    def autosquash_performed(self) -> bool:
        ...

    @property
    @abstractmethod
    def integration_requested(self) -> bool:
        ...

    @property
    @abstractmethod
    def integration_performed(self) -> bool:
        """True if integration has been performed.

        Note that "performed" here means "attempted", it might have failed."""
        ...

    @property
    @abstractmethod
    def strategy_used(self) -> Optional[api.review.IntegrationStrategy]:
        ...

    @property
    @abstractmethod
    def successful(self) -> Optional[bool]:
        ...

    @property
    @abstractmethod
    def error_message(self) -> Optional[str]:
        ...


async def fetch(critic: api.critic.Critic, request_id: int) -> ReviewIntegrationRequest:
    return await fetchImpl.get()(critic, request_id)


async def fetchAll(
    critic: api.critic.Critic,
    *,
    review: Optional[api.review.Review] = None,
    target_branch: Optional[api.branch.Branch] = None,
    performed: Optional[bool] = None,
    successful: Optional[bool] = None
) -> Sequence[ReviewIntegrationRequest]:
    return await fetchAllImpl.get()(
        critic, review, target_branch, performed, successful
    )


resource_name = table_name = "reviewintegrationrequests"


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, int], Awaitable[ReviewIntegrationRequest]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.review.Review],
            Optional[api.branch.Branch],
            Optional[bool],
            Optional[bool],
        ],
        Awaitable[Sequence[ReviewIntegrationRequest]],
    ]
] = FunctionRef()