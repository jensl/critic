# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

from critic import api
from critic import pubsub


class Error(Exception):
    pass


ResultType = TypeVar("ResultType")


class Request(Generic[ResultType], ABC):
    @abstractmethod
    async def dispatch(self, critic: api.critic.Critic) -> ResultType:
        ...

    async def issue(self) -> ResultType:
        async with pubsub.connect("extensiontasks/client") as client:
            request_handle = await client.request(
                pubsub.Payload(self), pubsub.ChannelName("extensiontasks")
            )
            try:
                await request_handle.delivery
                return await request_handle.response
            except Exception as error:
                raise Error(str(error)) from None


from .scanexternal import scan_external
from .readmanifest import read_manifest
from .fetchresource import fetch_resource
from .deleteextension import delete_extension
from .cloneexternal import clone_external
from .archiveversion import archive_version


__all__ = [
    "scan_external",
    "read_manifest",
    "fetch_resource",
    "delete_extension",
    "clone_external",
    "archive_version",
]
