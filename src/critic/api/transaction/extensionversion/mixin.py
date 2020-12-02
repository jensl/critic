from critic import api
from critic.gitaccess import SHA1
from critic.extensions.manifest import Manifest
from ..base import TransactionBase
from ..utils import requireAdministrator
from .modify import ModifyExtensionVersion


class Transaction(TransactionBase):
    @requireAdministrator
    async def createExtensionVersion(
        self, extension: api.extension.Extension, sha1: SHA1, manifest: Manifest
    ) -> ModifyExtensionVersion:
        return await ModifyExtensionVersion.create(self, extension, sha1, manifest)

    @requireAdministrator
    async def modifyExtensionVersion(
        self, version: api.extensionversion.ExtensionVersion
    ) -> ModifyExtensionVersion:
        return ModifyExtensionVersion(self, version)
