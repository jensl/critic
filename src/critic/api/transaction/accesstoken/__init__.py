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

from typing import Optional

from .. import LazyAPIObject
from critic import api


class CreatedAccessToken(LazyAPIObject, api_module=api.accesstoken):
    __profile: Optional[CreatedAccessControlProfile]

    def __init__(
        self, transaction: api.transaction.Transaction, user: api.user.User, token: str
    ) -> None:
        super().__init__(transaction)
        self.__user = user
        self.__profile = None
        self.token = token

    @property
    async def user(self) -> api.user.User:
        return self.__user

    @property
    async def profile(self) -> Optional[CreatedAccessControlProfile]:
        return self.__profile

    def setProfile(self, profile: CreatedAccessControlProfile) -> None:
        self.__profile = profile


from .modify import ModifyAccessToken
from ..accesscontrolprofile import CreatedAccessControlProfile

__all__ = ["create_accesstoken", "ModifyAccessToken"]
