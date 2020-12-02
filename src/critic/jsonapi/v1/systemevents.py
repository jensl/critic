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

from typing import Sequence, Union

from critic import api
from ..check import convert, input_spec, optional, anything
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id


class SystemEvents(
    ResourceClass[api.systemevent.SystemEvent], api_module=api.systemevent
):
    """The system settings."""

    @staticmethod
    async def json(
        parameters: Parameters, value: api.systemevent.SystemEvent
    ) -> JSONResult:
        """SystemEvent {
          "id": string, // the event's id
          "category": string, // the event's category
          "key": string, // the event's key
          "title": string, // the event's title
          "data": any, // the event's data
          "handled": boolean, // true if the event has been handled
        }"""

        return {
            "id": value.id,
            "category": value.category,
            "key": value.key,
            "title": value.title,
            "data": value.data,
            "handled": value.handled,
        }

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.systemevent.SystemEvent:
        """Retrieve one (or more) system events.

        EVENT_ID : string

        Retrieve a system event identified by its unique id."""

        return await api.systemevent.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Union[api.systemevent.SystemEvent, Sequence[api.systemevent.SystemEvent]]:
        """Retrieve all system events.

        catogory : CATEGORY : string

        Return only events in the specified category.

        key : KEY : string

        Return only events with the specified key.

        latest : LATEST : "yes" or "no"

        Return only the latest matching event."""

        critic = parameters.critic
        category_parameter = parameters.query.get("category")
        key_parameter = parameters.query.get("key")

        if category_parameter is None:
            raise UsageError.missingParameter("category")

        latest_parameter = parameters.query.get("latest", choices=("yes", "no"))
        if latest_parameter == "yes":
            if key_parameter is None:
                raise UsageError.missingParameter("key")
            return await api.systemevent.fetch(
                critic, category=category_parameter, key=key_parameter
            )

        return await api.systemevent.fetchAll(
            critic, category=category_parameter, key=key_parameter
        )

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> api.systemevent.SystemEvent:
        critic = parameters.critic

        converted = await convert(
            parameters,
            input_spec(category=str, key=str, title=str, data=optional(anything())),
            data,
        )

        async with api.transaction.start(critic) as transaction:
            return (
                await transaction.addSystemEvent(
                    converted["category"],
                    converted["key"],
                    converted["title"],
                    converted.get("data"),
                )
            ).subject
