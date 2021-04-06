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
from abc import abstractmethod

from typing import Awaitable, Callable, Collection, Optional, Sequence, Iterable

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="labeled access control profile"):
    """Base exception for all errors related to the LabeledAccessControlProfile
    class"""

    pass


class InvalidLabels(Error):
    """Raised when an invalid label set is used"""

    def __init__(self, value: Iterable[str]):
        """Constructor"""
        self.value = set(value)
        super().__init__("Invalid labels: %s" % "|".join(self.value))


class LabeledAccessControlProfile(api.APIObject):
    """Representation of a labeled access control profile selector"""

    RULE_VALUES = frozenset(["allow", "deny"])

    @property
    @abstractmethod
    def labels(self) -> Collection[str]:
        """The labels for which the access control profile is selected"""
        ...

    @property
    @abstractmethod
    async def profile(self) -> api.accesscontrolprofile.AccessControlProfile:
        """The access control profile that is selected"""
        ...


async def fetch(
    critic: api.critic.Critic, labels: Iterable[str]
) -> LabeledAccessControlProfile:
    """Fetch an LabeledAccessControlProfile object for the given labels"""
    return await fetchImpl.get()(critic, list(labels))


async def fetchAll(
    critic: api.critic.Critic,
    profile: Optional[api.accesscontrolprofile.AccessControlProfile] = None,
) -> Sequence[LabeledAccessControlProfile]:
    """Fetch LabeledAccessControlProfile objects for all labeled profiles
    selectors in the system"""
    return await fetchAllImpl.get()(critic, profile)


resource_name = table_name = "labeledaccesscontrolprofiles"

fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Sequence[str]],
        Awaitable[LabeledAccessControlProfile],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.accesscontrolprofile.AccessControlProfile]],
        Awaitable[Sequence[LabeledAccessControlProfile]],
    ]
] = FunctionRef()
