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

from abc import ABC, abstractmethod
from typing import Optional, Callable, Any, Union

from . import Transaction, LazyAPIObject, Query, Insert, Delete, Update, Modifier
from critic import api
from critic import dbaccess


class InvalidRuleValue(api.TransactionError):
    pass


class InvalidRequestMethod(api.TransactionError):
    pass


class InvalidPathPattern(api.TransactionError):
    pass


class InvalidRepositoryAccessType(api.TransactionError):
    pass


class InvalidExtensionAccessType(api.TransactionError):
    pass


class CreatedAccessControlProfile(
    LazyAPIObject, api_module=api.accesscontrolprofile,
):
    def __init__(
        self,
        transaction: Transaction,
        access_token: Optional[Union[api.accesstoken.AccessToken, CreatedAccessToken]],
    ) -> None:
        super().__init__(transaction)
        self.access_token = access_token


class ModifyExceptions(ABC):
    table_name: str

    def __init_subclass__(cls, table_name: str) -> None:
        cls.table_name = table_name

    def __init__(
        self,
        transaction: api.transaction.Transaction,
        profile: Union[
            api.accesscontrolprofile.AccessControlProfile, CreatedAccessControlProfile
        ],
    ) -> None:
        self.transaction = transaction
        self.profile = profile

    def delete(self, exception_id: int) -> None:
        self.transaction.items.append(
            Delete(f"accesscontrol_{self.table_name}").where(
                id=exception_id, profile=self.profile
            )
        )

    def deleteAll(self) -> None:
        self.transaction.items.append(
            Delete(f"accesscontrol_{self.table_name}").where(profile=self.profile)
        )

    def _insert(self, **columns: dbaccess.Parameter) -> None:
        self.transaction.items.append(
            Insert("accesscontrol_" + self.table_name).values(
                profile=self.profile, **columns
            )
        )

    @abstractmethod
    async def add(self, **kwargs: Any) -> None:
        ...


class ModifyHTTPExceptions(ModifyExceptions, table_name="http"):
    column_names = ("request_method", "path_pattern")

    async def add(self, **kwargs: Any) -> None:
        self._add(kwargs["request_method"], kwargs["path_pattern"])

    def _add(
        self,
        request_method: Optional[api.accesscontrolprofile.HTTPMethod],
        path_pattern: Optional[str],
    ) -> None:
        if request_method is not None:
            if request_method not in api.accesscontrolprofile.HTTP_METHODS:
                raise InvalidRequestMethod(request_method)

        if path_pattern is not None:
            import re

            try:
                re.compile(path_pattern)
            except re.error as error:
                raise InvalidPathPattern(f"{path_pattern!r}: {error}")

        self._insert(request_method=request_method, path_pattern=path_pattern)


class ModifyRepositoriesExceptions(ModifyExceptions, table_name="repositories"):
    async def add(self, **kwargs: Any) -> None:
        self._add(kwargs["access_type"], kwargs["repository"])

    def _add(
        self,
        access_type: Optional[api.accesscontrolprofile.RepositoryAccessType],
        repository: Optional[api.repository.Repository],
    ) -> None:
        assert repository is None or isinstance(repository, api.repository.Repository)

        if access_type is not None:
            if access_type not in api.accesscontrolprofile.REPOSITORY_ACCESS_TYPES:
                raise InvalidRepositoryAccessType(access_type)

        repository_id = repository.id if repository else None

        self._insert(access_type=access_type, repository_id=repository_id)


class ModifyExtensionsExceptions(ModifyExceptions, table_name="extension"):
    async def add(self, **kwargs: Any) -> None:
        await self._add(kwargs["access_type"], kwargs["extension"])

    async def _add(
        self,
        access_type: Optional[api.accesscontrolprofile.ExtensionAccessType],
        extension: Optional[api.extension.Extension],
    ) -> None:
        if access_type is not None:
            if access_type not in api.accesscontrolprofile.EXTENSION_ACCESS_TYPES:
                raise InvalidExtensionAccessType(access_type)

        extension_key = (await extension.key) if extension else None

        self._insert(access_type=access_type, extension_key=extension_key)


class ModifyAccessControlProfile(
    Modifier[api.accesscontrolprofile.AccessControlProfile, CreatedAccessControlProfile]
):
    def setTitle(self, value: str) -> None:
        self.transaction.items.append(Update(self.real).set(value=value))

    def setRule(
        self,
        category: api.accesscontrolprofile.CategoryType,
        value: api.accesscontrolprofile.RuleValue,
    ) -> None:
        self.transaction.items.append(Update(self.real).set(**{str(category): value}))

    def modifyHTTPExceptions(self) -> ModifyHTTPExceptions:
        return ModifyHTTPExceptions(self.transaction, self.subject)

    def modifyRepositoriesExceptions(self) -> ModifyRepositoriesExceptions:
        return ModifyRepositoriesExceptions(self.transaction, self.subject)

    def modifyExtensionsExceptions(self) -> ModifyExtensionsExceptions:
        return ModifyExtensionsExceptions(self.transaction, self.subject)

    def delete(self) -> None:
        self.transaction.items.append(Delete(self.real))

    @staticmethod
    def create(
        transaction: api.transaction.Transaction,
        *,
        callback: Callable[[api.APIObject], Any] = None,
    ) -> ModifyAccessControlProfile:
        profile = CreatedAccessControlProfile(transaction, None)

        if callback:
            profile.set_callback(callback)

        transaction.tables.add("accesscontrolprofiles")
        transaction.items.append(
            Query(
                """INSERT
                     INTO accesscontrolprofiles
                  DEFAULT VALUES""",
                returning="id",
                collector=profile,
            )
        )

        return ModifyAccessControlProfile(transaction, profile)


from .accesstoken import CreatedAccessToken
