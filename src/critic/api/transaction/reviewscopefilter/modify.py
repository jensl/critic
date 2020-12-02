from __future__ import annotations

from critic import api
from ..base import TransactionBase
from ..item import Delete
from ..modifier import Modifier
from .create import CreateReviewScopeFilter


class ModifyReviewScopeFilter(Modifier[api.reviewscopefilter.ReviewScopeFilter]):
    async def delete(self) -> None:
        await self.transaction.execute(Delete(self.subject))

    @staticmethod
    async def create(
        transaction: TransactionBase,
        repository: api.repository.Repository,
        scope: api.reviewscope.ReviewScope,
        path: str,
        included: bool,
    ) -> ModifyReviewScopeFilter:
        return ModifyReviewScopeFilter(
            transaction,
            await CreateReviewScopeFilter.make(
                transaction, repository, scope, path, included
            ),
        )
