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

import logging
import time
from abc import ABC, abstractmethod
from typing import Collection, Generic, Optional, Sequence, TypeVar

logger = logging.getLogger(__name__)

from critic import api
from critic import pubsub

from . import serialize_key, Key
from .job import Job
from .jobgroup import JobGroup
from .changeset import Changeset

GroupType = TypeVar("GroupType", bound=JobGroup)
ResponseType = TypeVar("ResponseType", covariant=True)


class RequestJob(Generic[GroupType, ResponseType], Job[GroupType]):
    __requests: Optional[Sequence[pubsub.OutgoingRequest]]
    __responses: Optional[Sequence[ResponseType]]

    def __init__(self, group: GroupType, key: Key):
        super().__init__(group, key)
        self.__requests = self.__responses = None

    @property
    def requests(self) -> Sequence[pubsub.OutgoingRequest]:
        assert self.__requests is not None
        return self.__requests

    @property
    def responses(self) -> Sequence[ResponseType]:
        assert self.__responses is not None
        return self.__responses

    @responses.setter
    def responses(self, responses: Sequence[ResponseType]) -> None:
        self.__responses = responses

    @abstractmethod
    async def issue_requests(
        self, client: pubsub.Client
    ) -> Sequence[pubsub.OutgoingRequest]:
        ...

    async def execute(self) -> None:
        self.__requests = await self.issue_requests(
            await self.group.service.pubsub_client
        )
