from __future__ import annotations

from typing import Optional

from critic import api
from ..item import Delete
from ..base import TransactionBase
from ..modifier import Modifier
from .create import CreateRebase


class ModifyRebase(Modifier[api.rebase.Rebase]):
    async def cancel(self) -> None:
        if not self.subject.is_pending:
            raise api.rebase.Error("Only pending rebases can be cancelled")

        await self.transaction.execute(Delete(self.subject))

    @staticmethod
    async def create(
        transaction: TransactionBase,
        review: api.review.Review,
        old_upstream: Optional[api.commit.Commit],
        new_upstream: Optional[api.commit.Commit],
        branch: Optional[api.branch.Branch],
    ) -> ModifyRebase:
        return ModifyRebase(
            transaction,
            await CreateRebase.make(
                transaction, review, old_upstream, new_upstream, branch
            ),
        )
