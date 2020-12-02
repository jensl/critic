from typing import Any

from critic import api
from .modify import ModifyUserSetting
from ..modifier import Modifier


class ModifyUser(Modifier[api.user.User]):
    async def defineSetting(
        self, scope: str, name: str, value: Any
    ) -> ModifyUserSetting:
        return await ModifyUserSetting.create(
            self.transaction, self.subject, scope, name, value
        )

    async def modifyUserSetting(
        self, usersetting: api.usersetting.UserSetting
    ) -> ModifyUserSetting:
        if self.subject != await usersetting.user:
            raise api.user.Error(
                "Cannot modify a user setting belonging to another user"
            )
        return ModifyUserSetting(self.transaction, usersetting)
