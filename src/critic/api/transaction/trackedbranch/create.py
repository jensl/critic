from __future__ import annotations

from critic import api
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject


class CreateTrackedBranch(
    CreateAPIObject[api.trackedbranch.TrackedBranch], api_module=api.trackedbranch
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        repository: api.repository.Repository,
        url: str,
        remote_name: str,
        local_name: str,
        delay: int,
    ) -> api.trackedbranch.TrackedBranch:
        return await CreateTrackedBranch(transaction).insert(
            repository=repository,
            local_name=local_name,
            remote=url,
            remote_name=remote_name,
            forced=True,
            delay=delay,
        )
