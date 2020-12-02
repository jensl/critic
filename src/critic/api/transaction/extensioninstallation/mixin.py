from critic import api
from ..base import TransactionBase
from ..modifier import Modifier
from ..utils import requireAdministrator
from .modify import ModifyExtensionInstallation


class ModifyUser(Modifier[api.user.User]):
    async def installExtension(
        self,
        extension: api.extension.Extension,
        version: api.extensionversion.ExtensionVersion,
    ) -> ModifyExtensionInstallation:
        return await ModifyExtensionInstallation.create(
            self.transaction, extension, version, user=self.subject
        )

    async def modifyExtensionInstallation(
        self, installation: api.extensioninstallation.ExtensionInstallation
    ) -> ModifyExtensionInstallation:
        if await installation.user != self.subject:
            raise api.user.Error(
                "Cannot modify extension installation beloning to another user"
            )
        return ModifyExtensionInstallation(self.transaction, installation)


class Transaction(TransactionBase):
    @requireAdministrator
    async def installExtension(
        self,
        extension: api.extension.Extension,
        version: api.extensionversion.ExtensionVersion,
    ) -> ModifyExtensionInstallation:
        return await ModifyExtensionInstallation.create(self, extension, version)

    @requireAdministrator
    async def modifyExtensionInstallation(
        self, installation: api.extensioninstallation.ExtensionInstallation
    ) -> ModifyExtensionInstallation:
        if not installation.is_universal:
            raise api.APIError("installation is not universal")
        return ModifyExtensionInstallation(self, installation)
