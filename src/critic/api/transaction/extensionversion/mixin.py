from critic import api
from critic.gitaccess import SHA1
from critic.extensions.manifest import Manifest
from ..base import TransactionBase
from ..modifier import Modifier
from ..utils import requireAdministrator
from .modify import ModifyExtensionVersion


class Transaction(TransactionBase):
    @requireAdministrator
    async def createExtensionVersion(
        self,
        extension: api.extension.Extension,
        name: str,
        sha1: SHA1,
        manifest: Manifest,
    ) -> ModifyExtensionVersion:
        return await ModifyExtensionVersion.create(
            self, extension, name, sha1, manifest
        )

    @requireAdministrator
    async def modifyExtensionVersion(
        self, version: api.extensionversion.ExtensionVersion
    ) -> ModifyExtensionVersion:
        return ModifyExtensionVersion(self, version)


class ModifyExtension(Modifier[api.extension.Extension]):
    async def createExtensionVersion(
        self, name: str, sha1: SHA1, manifest: Manifest
    ) -> ModifyExtensionVersion:
        return await ModifyExtensionVersion.create(
            self.transaction, self.subject, sha1, manifest
        )

    async def modifyExtensionVersion(
        self, version: api.extensionversion.ExtensionVersion
    ) -> ModifyExtensionVersion:
        if self.subject != await version.extension:
            raise api.extension.Error(
                "Cannot modify extension version belonging to a different extension"
            )
        return ModifyExtensionVersion(self.transaction, version)
