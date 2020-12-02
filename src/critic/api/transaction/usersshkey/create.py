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
import sshpubkeys
from typing import Optional

logger = logging.getLogger(__name__)

from critic import api
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject


class CreatedUserSSHKey(
    CreateAPIObject[api.usersshkey.UserSSHKey], api_module=api.usersshkey
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        user: api.user.User,
        key_type: str,
        key: str,
        comment: Optional[str],
    ) -> api.usersshkey.UserSSHKey:
        try:
            base64.b64decode(key)
        except Exception:
            raise api.usersshkey.Error(
                "Invalid key data: expected valid base64 encoding"
            )

        try:
            sshpubkeys.SSHKey(f"{key_type} {key}")
        except sshpubkeys.InvalidKeyLengthError:
            raise api.usersshkey.Error("Invalid key length")
        except sshpubkeys.InvalidTypeError:
            raise api.usersshkey.Error("Invalid key type")
        except sshpubkeys.MalformedDataError:
            raise api.usersshkey.Error("Malformed key data")
        except Exception:
            raise api.usersshkey.Error("Invalid key")

        return await CreatedUserSSHKey(transaction).insert(
            uid=user, type=key_type, key=key, comment=comment
        )
