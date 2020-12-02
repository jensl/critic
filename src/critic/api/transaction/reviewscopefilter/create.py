from __future__ import annotations

from critic import api
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject


class CreateReviewScopeFilter(
    CreateAPIObject[api.reviewscopefilter.ReviewScopeFilter],
    api_module=api.reviewscopefilter,
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        repository: api.repository.Repository,
        scope: api.reviewscope.ReviewScope,
        path: str,
        included: bool,
    ) -> api.reviewscopefilter.ReviewScopeFilter:
        return await CreateReviewScopeFilter(transaction).insert(
            repository=repository, scope=scope, path=path, included=included
        )
