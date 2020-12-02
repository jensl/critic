from __future__ import annotations

from critic import api
from ..base import TransactionBase
from ..modifier import Modifier
from .create import CreateTrackedBranch


class ModifyTrackedBranch(Modifier[api.trackedbranch.TrackedBranch]):
    @staticmethod
    async def create(
        transaction: TransactionBase,
        repository: api.repository.Repository,
        url: str,
        remote_name: str,
        local_name: str,
        delay: int,
    ) -> ModifyTrackedBranch:
        return ModifyTrackedBranch(
            transaction,
            await CreateTrackedBranch.make(
                transaction, repository, url, remote_name, local_name, delay
            ),
        )
