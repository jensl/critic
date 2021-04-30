# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2019 the Critic contributors, Opera Software ASA
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

from critic import api
from critic.gitaccess import SHA1
from critic.extensions.manifest import Manifest
from ..base import TransactionBase
from ..modifier import Modifier
from ..extensioncall.mixin import ModifyVersion as ExtensionCallMixin
from .create import CreateExtensionVersion


class ModifyExtensionVersion(
    ExtensionCallMixin, Modifier[api.extensionversion.ExtensionVersion]
):
    @staticmethod
    async def create(
        transaction: TransactionBase,
        extension: api.extension.Extension,
        name: str,
        sha1: SHA1,
        manifest: Manifest,
    ) -> ModifyExtensionVersion:
        return ModifyExtensionVersion(
            transaction,
            await CreateExtensionVersion.make(
                transaction, extension, name, sha1, manifest
            ),
        )
