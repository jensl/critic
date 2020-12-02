from critic import api
from .modify import ModifyAccessControlProfile
from ..base import TransactionBase


class Transaction(TransactionBase):
    async def createAccessControlProfile(
        self,
    ) -> ModifyAccessControlProfile:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return await ModifyAccessControlProfile.create(self)

    def modifyAccessControlProfile(
        self, profile: api.accesscontrolprofile.AccessControlProfile
    ) -> ModifyAccessControlProfile:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return ModifyAccessControlProfile(self, profile)
