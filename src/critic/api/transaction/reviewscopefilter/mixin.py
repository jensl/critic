from critic import api
from ..base import TransactionBase
from .modify import ModifyReviewScopeFilter


class Transaction(TransactionBase):
    async def createReviewScopeFilter(
        self,
        repository: api.repository.Repository,
        scope: api.reviewscope.ReviewScope,
        path: str,
        included: bool,
    ) -> ModifyReviewScopeFilter:
        return await ModifyReviewScopeFilter.create(
            self, repository, scope, path, included
        )

    def modifyReviewScopeFilter(
        self, scope_filter: api.reviewscopefilter.ReviewScopeFilter
    ) -> ModifyReviewScopeFilter:
        return ModifyReviewScopeFilter(self, scope_filter)
