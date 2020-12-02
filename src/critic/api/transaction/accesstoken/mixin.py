from typing import Optional, Tuple

from critic import api
from .modify import ModifyAccessToken
from ..base import TransactionBase
from ..modifier import Modifier


class ModifyUser(Modifier[api.user.User]):
    async def createAccessToken(
        self, title: Optional[str]
    ) -> Tuple[ModifyAccessToken, str]:
        if self.critic.access_token:
            # Don't allow creation of access tokens when an access token was
            # used to authenticate.  This could be used to effectively bypass
            # access restrictions set on the access token, unless we make sure
            # the created access token's access control profile is at least
            # equally strict, which is difficult.
            raise api.PermissionDenied("Access token used to authenticate")

        return await ModifyAccessToken.create(
            self.transaction, "user", title, user=self.subject
        )

    async def modifyAccessToken(
        self, access_token: api.accesstoken.AccessToken
    ) -> ModifyAccessToken:
        if await access_token.user != self.subject:
            raise api.PermissionDenied(
                "Cannot modify access token belonging to another user"
            )

        if self.transaction.critic.access_token:
            # Don't allow any modifications of access tokens when an access
            # token was used to authenticate.  This could be used to effectively
            # bypass access restrictions set on the access token, unless we make
            # sure the modified access token's access control profile is at
            # least equally strict, which is difficult.
            raise api.PermissionDenied("Access token used to authenticate")

        return ModifyAccessToken(self.transaction, access_token)


class Transaction(TransactionBase):
    async def createAccessToken(
        self, access_type: api.accesstoken.AccessType, title: Optional[str]
    ) -> Tuple[ModifyAccessToken, str]:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return await ModifyAccessToken.create(self, access_type, title)

    def modifyAccessToken(
        self, access_token: api.accesstoken.AccessToken
    ) -> ModifyAccessToken:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return ModifyAccessToken(self, access_token)
