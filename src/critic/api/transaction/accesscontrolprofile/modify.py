from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from critic import api
from critic import dbaccess
from ..base import TransactionBase
from ..item import Delete, Insert, Update
from ..modifier import Modifier
from .create import CreateAccessControlProfile


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


class ModifyExceptions(ABC):
    table_name: str

    def __init_subclass__(cls, table_name: str) -> None:
        cls.table_name = table_name

    def __init__(
        self,
        transaction: TransactionBase,
        profile: api.accesscontrolprofile.AccessControlProfile,
    ) -> None:
        self.transaction = transaction
        self.profile = profile

    async def delete(self, exception_id: int) -> None:
        await self.transaction.execute(
            Delete(f"accesscontrol_{self.table_name}").where(
                id=exception_id, profile=self.profile
            )
        )

    async def deleteAll(self) -> None:
        await self.transaction.execute(
            Delete(f"accesscontrol_{self.table_name}").where(profile=self.profile)
        )

    async def _insert(self, **columns: dbaccess.Parameter) -> None:
        await self.transaction.execute(
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
        await self._add(kwargs["request_method"], kwargs["path_pattern"])

    async def _add(
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

        await self._insert(request_method=request_method, path_pattern=path_pattern)


class ModifyRepositoriesExceptions(ModifyExceptions, table_name="repositories"):
    async def add(self, **kwargs: Any) -> None:
        await self._add(kwargs["access_type"], kwargs["repository"])

    async def _add(
        self,
        access_type: Optional[api.accesscontrolprofile.RepositoryAccessType],
        repository: Optional[api.repository.Repository],
    ) -> None:
        assert repository is None or isinstance(repository, api.repository.Repository)

        if access_type is not None:
            if access_type not in api.accesscontrolprofile.REPOSITORY_ACCESS_TYPES:
                raise InvalidRepositoryAccessType(access_type)

        repository_id = repository.id if repository else None

        await self._insert(access_type=access_type, repository_id=repository_id)


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

        await self._insert(access_type=access_type, extension_key=extension_key)


class ModifyAccessControlProfile(
    Modifier[api.accesscontrolprofile.AccessControlProfile]
):
    async def setTitle(self, value: str) -> None:
        await self.transaction.execute(Update(self.subject).set(value=value))

    async def setRule(
        self,
        category: api.accesscontrolprofile.CategoryType,
        value: api.accesscontrolprofile.RuleValue,
    ) -> None:
        await self.transaction.execute(
            Update(self.subject).set(**{str(category): value})
        )

    def modifyHTTPExceptions(self) -> ModifyHTTPExceptions:
        return ModifyHTTPExceptions(self.transaction, self.subject)

    def modifyRepositoriesExceptions(self) -> ModifyRepositoriesExceptions:
        return ModifyRepositoriesExceptions(self.transaction, self.subject)

    def modifyExtensionsExceptions(self) -> ModifyExtensionsExceptions:
        return ModifyExtensionsExceptions(self.transaction, self.subject)

    async def delete(self) -> None:
        await self.transaction.execute(Delete(self.subject))

    @staticmethod
    async def create(
        transaction: TransactionBase,
        access_token: Optional[api.accesstoken.AccessToken] = None,
    ) -> ModifyAccessControlProfile:
        return ModifyAccessControlProfile(
            transaction,
            await CreateAccessControlProfile.make(transaction, access_token),
        )
