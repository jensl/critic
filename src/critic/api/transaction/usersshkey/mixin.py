from typing import Optional

from critic import api
from .modify import ModifyUserSSHKey
from ..modifier import Modifier


class ModifyUser(Modifier[api.user.User]):
    async def addSSHKey(
        self, key_type: str, key: str, comment: Optional[str] = None
    ) -> ModifyUserSSHKey:
        return await ModifyUserSSHKey.create(
            self.transaction, self.subject, key_type, key, comment
        )

    async def modifySSHKey(
        self, usersshkey: api.usersshkey.UserSSHKey
    ) -> ModifyUserSSHKey:
        if self.subject != await usersshkey.user:
            raise api.user.Error("Cannot modify another user's SSH key")
        return ModifyUserSSHKey(self.transaction, usersshkey)
