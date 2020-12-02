from __future__ import annotations

from critic import api
from .createapiobject import CreateAPIObject


class CreateExternalAccount(
    CreateAPIObject[api.externalaccount.ExternalAccount], api_module=api.externalaccount
):
    pass
