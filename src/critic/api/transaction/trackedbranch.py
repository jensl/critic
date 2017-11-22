from __future__ import annotations

from typing import Union

from . import Transaction, LazyAPIObject, Delete, Query, Modifier
from critic import api


class CreatedTrackedBranch(LazyAPIObject, api_module=api.trackedbranch):
    @staticmethod
    async def make(
        transaction: Transaction,
        repository: Union[api.repository.Repository, CreatedRepository],
        url: str,
        remote_name: str,
        local_name: str,
        delay: int,
    ) -> CreatedTrackedBranch:
        created_tracked_branch = CreatedTrackedBranch(transaction)
        transaction.items.append(
            Query(
                """INSERT
                     INTO trackedbranches (
                            repository, local_name, remote, remote_name, forced,
                            delay
                          )
                   VALUES ({repository}, {local_name}, {url}, {remote_name}, TRUE,
                           INTERVAL {delay})""",
                repository=repository,
                local_name=local_name,
                url=url,
                remote_name=remote_name,
                delay=f"{delay} seconds",
                returning="id",
                collector=created_tracked_branch,
            )
        )
        return created_tracked_branch


class ModifyTrackedBranch(
    Modifier[api.trackedbranch.TrackedBranch, CreatedTrackedBranch]
):
    def delete(self) -> None:
        self.transaction.items.append(Delete(self.real))

    @staticmethod
    async def create(
        transaction: Transaction,
        repository: Union[api.repository.Repository, CreatedRepository],
        url: str,
        remote_name: str,
        local_name: str,
        delay: int,
    ) -> ModifyTrackedBranch:
        return ModifyTrackedBranch(
            transaction,
            await CreatedTrackedBranch.make(
                transaction, repository, url, remote_name, local_name, delay
            ),
        )


from .repository import CreatedRepository
