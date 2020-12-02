from __future__ import annotations

from typing import Collection

from critic import api
from ..base import TransactionBase
from ..item import Delete
from ..modifier import Modifier
from .create import CreatedReviewFilter


class ModifyReviewFilter(Modifier[api.reviewfilter.ReviewFilter]):
    async def delete(self) -> None:
        await self.transaction.execute(Delete(self.subject))

    @staticmethod
    async def create(
        transaction: TransactionBase,
        review: api.review.Review,
        subject: api.user.User,
        filter_type: api.reviewfilter.FilterType,
        path: str,
        default_scope: bool,
        scopes: Collection[api.reviewscope.ReviewScope],
    ) -> ModifyReviewFilter:
        return ModifyReviewFilter(
            transaction,
            await CreatedReviewFilter.make(
                transaction, review, subject, filter_type, path, default_scope, scopes
            ),
        )
