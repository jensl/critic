from critic import api
from .modify import ModifyUserEmail
from ..modifier import Modifier


class ModifyUser(Modifier[api.user.User]):
    async def addEmailAddress(
        self, address: str, *, status: api.useremail.Status = "unverified"
    ) -> ModifyUserEmail:
        return await ModifyUserEmail.create(
            self.transaction, self.subject, address, status
        )

    async def modifyEmailAddress(
        self, useremail: api.useremail.UserEmail
    ) -> ModifyUserEmail:
        if self.subject != await useremail.user:
            raise api.user.Error("Cannot modify user email belonging to another user")
        return ModifyUserEmail(self.transaction, useremail)
