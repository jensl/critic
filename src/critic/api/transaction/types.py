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

from typing import (
    Optional,
    Callable,
    Any,
    Tuple,
    Protocol,
    Sequence,
    Coroutine,
)

from . import protocol

from critic import pubsub


class Publisher(Protocol):
    async def publish(
        self,
    ) -> Optional[Tuple[Sequence[pubsub.ChannelName], protocol.PublishedMessage]]:
        ...


class SimplePublisher(Publisher):
    def __init__(self, message: protocol.PublishedMessage):
        self.message = message

    async def publish(
        self,
    ) -> Tuple[Sequence[pubsub.ChannelName], protocol.PublishedMessage]:
        return self.message.scopes(), self.message


AsyncCallback = Callable[[], Coroutine[Any, Any, None]]
