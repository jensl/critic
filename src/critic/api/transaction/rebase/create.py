from __future__ import annotations

from typing import Optional

from ..base import TransactionBase
from ..review import CreateReviewObject

from critic import api


class CreateRebase(CreateReviewObject[api.rebase.Rebase], api_module=api.rebase):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        review: api.review.Review,
        old_upstream: Optional[api.commit.Commit],
        new_upstream: Optional[api.commit.Commit],
        branch: Optional[api.branch.Branch],
    ) -> api.rebase.Rebase:
        return await CreateRebase(transaction, review).insert(
            review=review,
            old_upstream=old_upstream,
            new_upstream=new_upstream,
            uid=transaction.critic.effective_user,
            branch=branch,
        )
