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

import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

from . import CreatedAccessToken
from .. import Insert, Transaction
from ..accesscontrolprofile import CreatedAccessControlProfile
from critic import api
from critic import auth


def create_accesstoken(
    transaction: Transaction,
    access_type: api.accesstoken.AccessType,
    title: Optional[str],
    user: Optional[api.user.User],
) -> CreatedAccessToken:
    critic = transaction.critic
    if access_type == "user":
        assert user is not None
        api.PermissionDenied.raiseUnlessUser(critic, user)
    else:
        assert user is None
        api.PermissionDenied.raiseUnlessAdministrator(critic)
        if access_type == "anonymous":
            user = api.user.anonymous(transaction.critic)
        else:
            assert access_type == "system"
            user = api.user.system(transaction.critic)

    token = auth.getToken(encode=base64.b64encode, length=33)

    access_token = CreatedAccessToken(transaction, user, token).insert(
        access_type=access_type, uid=user, token=token, title=title
    )
    access_token.setProfile(
        CreatedAccessControlProfile(transaction, access_token).insert(
            access_token=access_token
        )
    )

    return access_token
