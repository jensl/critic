from typing import Collection

from critic import api
from ..modifier import Modifier
from .modify import ModifyReviewFilter


class ModifyReview(Modifier[api.review.Review]):
    async def createFilter(
        self,
        subject: api.user.User,
        filter_type: api.reviewfilter.FilterType,
        path: str,
        default_scope: bool,
        scopes: Collection[api.reviewscope.ReviewScope],
    ) -> ModifyReviewFilter:
        return await ModifyReviewFilter.create(
            self.transaction,
            self.subject,
            subject,
            filter_type,
            path,
            default_scope,
            scopes,
        )

    async def modifyFilter(
        self, filter: api.reviewfilter.ReviewFilter
    ) -> ModifyReviewFilter:
        if await filter.review != self.subject:
            raise api.review.Error("Cannot modify filter belonging to another review")
        return ModifyReviewFilter(self.transaction, filter)
