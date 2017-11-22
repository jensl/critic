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

from typing import Sequence, Optional, Union

from critic import api
from critic import jsonapi


class SystemEvents(
    jsonapi.ResourceClass[api.systemevent.SystemEvent], api_module=api.systemevent
):
    """The system settings."""

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.systemevent.SystemEvent
    ) -> jsonapi.JSONResult:
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

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.systemevent.SystemEvent:
        """Retrieve one (or more) system events.

           EVENT_ID : string

           Retrieve a system event identified by its unique id."""

        return await api.systemevent.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[api.systemevent.SystemEvent, Sequence[api.systemevent.SystemEvent]]:
        """Retrieve all system events.

           catogory : CATEGORY : string

           Return only events in the specified category.

           key : KEY : string

           Return only events with the specified key.

           latest : LATEST : "yes" or "no"

           Return only the latest matching event."""

        critic = parameters.critic
        category_parameter = parameters.getQueryParameter("category")
        key_parameter = parameters.getQueryParameter("key")

        if category_parameter is None:
            raise jsonapi.UsageError.missingParameter("category")

        latest_parameter = parameters.getQueryParameter("latest", choices=("yes", "no"))
        if latest_parameter == "yes":
            if key_parameter is None:
                raise jsonapi.UsageError.missingParameter("key")
            return await api.systemevent.fetch(
                critic, category=category_parameter, key=key_parameter
            )

        return await api.systemevent.fetchAll(
            critic, category=category_parameter, key=key_parameter
        )

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.systemevent.SystemEvent:
        critic = parameters.critic

        converted = await jsonapi.convert(
            parameters,
            {
                "category": str,
                "key": str,
                "title": str,
                "data?": jsonapi.check.TypeChecker(),
            },
            data,
        )

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.addSystemEvent(
                converted["category"],
                converted["key"],
                converted["title"],
                converted.get("data"),
            )

        return await modifier
