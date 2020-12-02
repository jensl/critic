from critic import api
from ..base import TransactionBase
from ..modifier import Modifier
from .modify import ModifyExtension


class ModifyUser(Modifier[api.user.User]):
    async def createExtension(self, name: str, url: str) -> ModifyExtension:
        return await ModifyExtension.create(
            self.transaction, name, url, publisher=self.subject
        )

    async def modifyExtension(
        self, extension: api.extension.Extension
    ) -> ModifyExtension:
        if self.subject != await extension.publisher:
            raise api.user.Error("Cannot modify extension published by another user")
        return ModifyExtension(self.transaction, extension, self.subject)


class Transaction(TransactionBase):
    async def createExtension(self, name: str, url: str) -> ModifyExtension:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return await ModifyExtension.create(self, name, url)

    async def modifyExtension(
        self, subject: api.extension.Extension
    ) -> ModifyExtension:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return ModifyExtension(self, subject, None)
