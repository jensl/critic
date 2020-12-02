from __future__ import annotations

from critic import api
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject


class CreateReviewScope(
    CreateAPIObject[api.reviewscope.ReviewScope], api_module=api.reviewscope
):
    @staticmethod
    async def make(
        transaction: TransactionBase, name: str
    ) -> api.reviewscope.ReviewScope:
        return await CreateReviewScope(transaction).insert(name=name)
