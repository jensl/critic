from __future__ import annotations

from critic import api
from ..base import TransactionBase
from ..item import Delete
from ..modifier import Modifier
from .create import CreateReviewScope


class ModifyReviewScope(Modifier[api.reviewscope.ReviewScope]):
    async def delete(self) -> None:
        await self.transaction.execute(Delete(self.subject))

    @staticmethod
    async def create(transaction: TransactionBase, name: str) -> ModifyReviewScope:
        return ModifyReviewScope(
            transaction, await CreateReviewScope.make(transaction, name)
        )
