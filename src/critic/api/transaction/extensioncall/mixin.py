from critic import api
from critic.protocol.extensionhost import CallRequest
from ..modifier import Modifier
from .modify import ModifyExtensionCall


class ModifyVersion(Modifier[api.extensionversion.ExtensionVersion]):
    async def recordCallRequest(self, request: CallRequest) -> ModifyExtensionCall:
        return await ModifyExtensionCall.create(self.transaction, self.subject, request)

    async def modifyExtensionCall(
        self, call: api.extensioncall.ExtensionCall
    ) -> ModifyExtensionCall:
        if self.subject != await call.version:
            raise api.extension.Error(
                "Cannot modify extension call belonging to a different extension version"
            )
        return ModifyExtensionCall(self.transaction, call)
