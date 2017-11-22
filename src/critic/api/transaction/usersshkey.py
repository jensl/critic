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
from typing import Optional, Union

logger = logging.getLogger(__name__)

from . import Transaction, Delete, Insert, Update, LazyAPIObject, Modifier
from .user import CreatedUser, CreatedUserObject
from critic import api


class CreatedUserSSHKey(CreatedUserObject, api_module=api.usersshkey):
    @staticmethod
    def make(
        transaction: Transaction,
        user: Union[api.user.User, CreatedUser],
        key_type: str,
        key: str,
        comment: Optional[str],
    ) -> CreatedUserSSHKey:
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

        return CreatedUserSSHKey(transaction, user).insert(
            uid=user, type=key_type, key=key, comment=comment
        )


class ModifyUserSSHKey(Modifier[api.usersshkey.UserSSHKey, CreatedUserSSHKey]):
    def setComment(self, value: str) -> None:
        self.transaction.items.append(Update(self.subject).set(comment=value))

    def delete(self) -> None:
        self.transaction.items.append(Delete(self.subject))

    @staticmethod
    def create(
        transaction: Transaction,
        user: Union[api.user.User, CreatedUser],
        key_type: str,
        key: str,
        comment: str = None,
    ) -> ModifyUserSSHKey:
        return ModifyUserSSHKey(
            transaction,
            CreatedUserSSHKey.make(transaction, user, key_type, key, comment),
        )
