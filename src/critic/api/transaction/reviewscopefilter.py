from __future__ import annotations

from typing import Union

from . import Transaction, Delete, Modifier
from .lazy import LazyAPIObject
from .reviewscope import CreatedReviewScope

from critic import api


class CreatedReviewScopeFilter(LazyAPIObject, api_module=api.reviewscopefilter):
    @staticmethod
    def make(
        transaction: Transaction,
        repository: api.repository.Repository,
        scope: Union[api.reviewscope.ReviewScope, CreatedReviewScope],
        path: str,
        included: bool,
    ) -> CreatedReviewScopeFilter:
        return CreatedReviewScopeFilter(transaction).insert(
            repository=repository, scope=scope, path=path, included=included
        )


class ModifyReviewScopeFilter(
    Modifier[api.reviewscopefilter.ReviewScopeFilter, CreatedReviewScopeFilter]
):
    def delete(self) -> None:
        self.transaction.items.append(Delete(self.real))

    @staticmethod
    def create(
        transaction: Transaction,
        repository: api.repository.Repository,
        scope: Union[api.reviewscope.ReviewScope, CreatedReviewScope],
        path: str,
        included: bool,
    ) -> ModifyReviewScopeFilter:
        return ModifyReviewScopeFilter(
            transaction,
            CreatedReviewScopeFilter.make(
                transaction, repository, scope, path, included
            ),
        )
