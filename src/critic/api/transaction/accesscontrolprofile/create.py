from typing import Optional

from critic import api
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject


class CreateAccessControlProfile(
    CreateAPIObject[api.accesscontrolprofile.AccessControlProfile],
    api_module=api.accesscontrolprofile,
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        access_token: Optional[api.accesstoken.AccessToken],
    ) -> api.accesscontrolprofile.AccessControlProfile:
        return await CreateAccessControlProfile(transaction).insert(
            access_token=access_token
        )
