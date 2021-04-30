from typing import Any, Optional

from critic import api
from ..base import TransactionBase
from ..modifier import Modifier
from .modify import ModifySetting


class ModifyUser(Modifier[api.user.User]):
    async def defineSetting(
        self,
        scope: str,
        name: str,
        value: Any,
        value_bytes: Optional[bytes],
        repository: Optional[api.repository.Repository],
        branch: Optional[api.branch.Branch],
        review: Optional[api.review.Review],
        extension: Optional[api.extension.Extension],
    ) -> ModifySetting:
        return await ModifySetting.create(
            self.transaction,
            scope,
            name,
            value,
            value_bytes,
            self.subject,
            repository,
            branch,
            review,
            extension,
        )

    async def modifySetting(self, setting: api.setting.Setting) -> ModifySetting:
        if self.subject != await setting.user:
            raise api.user.Error("Cannot modify a setting belonging to another user")
        return ModifySetting(self.transaction, setting)


class Transaction(TransactionBase):
    async def defineSetting(
        self,
        scope: str,
        name: str,
        value: Any,
        value_bytes: Optional[bytes],
        user: Optional[api.user.User],
        repository: Optional[api.repository.Repository],
        branch: Optional[api.branch.Branch],
        review: Optional[api.review.Review],
        extension: Optional[api.extension.Extension],
    ) -> ModifySetting:
        return await ModifySetting.create(
            self,
            scope,
            name,
            value,
            value_bytes,
            user,
            repository,
            branch,
            review,
            extension,
        )

    async def modifySetting(self, setting: api.setting.Setting) -> ModifySetting:
        user = await setting.user
        if user:
            api.PermissionDenied.raiseUnlessUser(self.critic, user)
        else:
            api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return ModifySetting(self, setting)
