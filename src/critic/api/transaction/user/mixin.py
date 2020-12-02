from typing import Optional

from critic import api

from ..base import TransactionBase
from .modify import ModifyUser


class Transaction(TransactionBase):
    async def createUser(
        self,
        name: str,
        fullname: str,
        email: Optional[str],
        *,
        email_status: Optional[api.useremail.Status] = None,
        hashed_password: Optional[str] = None,
        status: api.user.Status = "current",
        external_account: Optional[api.externalaccount.ExternalAccount] = None,
    ) -> ModifyUser:
        # Note: Access control is in create_user(), as it is non-trivial.
        return await ModifyUser.create(
            self,
            name,
            fullname,
            email,
            email_status,
            hashed_password,
            status,
            external_account,
        )

    def modifyUser(self, subject: api.user.User) -> ModifyUser:
        api.PermissionDenied.raiseUnlessUser(self.critic, subject)
        return ModifyUser(self, subject)
