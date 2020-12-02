from critic import api
from ..base import TransactionBase
from .modify import ModifyReviewScope


class Transaction(TransactionBase):
    async def createReviewScope(self, name: str) -> ModifyReviewScope:
        return await ModifyReviewScope.create(self, name)

    def modifyReviewScope(
        self, scope: api.reviewscope.ReviewScope
    ) -> ModifyReviewScope:
        return ModifyReviewScope(self, scope)
