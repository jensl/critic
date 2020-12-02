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

from typing import Sequence

from critic import api
from ..check import convert
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult

api_module = api.labeledaccesscontrolprofile
value_class = api_module.LabeledAccessControlProfile


class LabeledAccessControlProfiles(ResourceClass[value_class], api_module=api_module):
    """The labeled access control profile selectorss of this system."""

    contexts = (None, "accesscontrolprofiles")

    @staticmethod
    async def json(parameters: Parameters, value: value_class) -> JSONResult:
        """LabeledAccessControlProfile {
          "labels": [string],
          "profile": integer
        }"""

        # Make sure that only administrator users can access.
        api.PermissionDenied.raiseUnlessAdministrator(parameters.critic)

        return {"labels": value.labels, "profile": value.profile}

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> value_class:
        """Retrieve one (or more) access control profiles.

        LABELS : string

        Retrieve an access control profile identified by the profile
        selectors's set of labels. Separate labels with pipe ('|')
        characters."""

        return await api_module.fetch(parameters.critic, labels=argument.split("|"))

    @staticmethod
    async def multiple(parameters: Parameters) -> Sequence[value_class]:
        """Retrieve all labeled access control profile selectors in the system.

        profile : PROFILE_ID : integer

        Include only selectors selecting the given profile, identified by its
        unique numeric id."""
        profile = await parameters.deduce(api.accesscontrolprofile.AccessControlProfile)
        return await api_module.fetchAll(parameters.critic, profile=profile)

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> value_class:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {"labels": [str], "profile": api.accesscontrolprofile.AccessControlProfile},
            data,
        )

        async with api.transaction.start(critic) as transaction:
            return (
                await transaction.createLabeledAccessControlProfile(
                    converted["labels"], converted["profile"]
                )
            ).subject
