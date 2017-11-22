from __future__ import annotations

from . import LazyAPIObject
from critic import api


class CreatedExternalAccount(LazyAPIObject, api_module=api.externalaccount):
    pass
