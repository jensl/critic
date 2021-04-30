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

import json
import logging
from typing import Collection

from critic import dbaccess

logger = logging.getLogger(__name__)

from critic import api
from critic.gitaccess import SHA1
from critic.extensions.manifest import Manifest
from ..createapiobject import CreateAPIObject
from ..base import TransactionBase


class InsertManifest:
    def __init__(
        self, version: api.extensionversion.ExtensionVersion, manifest: Manifest
    ):
        self.__version = version
        self.__manifest = manifest
        self.__table_names = set()
        for role in manifest.roles:
            self.__table_names.update(role.table_names)

    @property
    def table_names(self) -> Collection[str]:
        return self.__table_names

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor
    ) -> None:
        for role in self.__manifest.roles:
            await role.install(cursor, self.__version.id)


class CreateExtensionVersion(
    CreateAPIObject[api.extensionversion.ExtensionVersion],
    api_module=api.extensionversion,
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        extension: api.extension.Extension,
        name: str,
        sha1: SHA1,
        manifest: Manifest,
    ) -> api.extensionversion.ExtensionVersion:
        version = await CreateExtensionVersion(transaction).insert(
            extension=extension,
            name=name,
            sha1=sha1,
            invalid=False,
            manifest=json.dumps(manifest.configuration),
        )

        await transaction.execute(InsertManifest(version, manifest))

        return version
