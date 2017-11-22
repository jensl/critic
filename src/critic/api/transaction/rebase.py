from __future__ import annotations

from typing import Optional

from . import Transaction, Delete, Modifier
from .review import CreatedReviewObject

from critic import api


class CreatedRebase(CreatedReviewObject, api_module=api.log.rebase):
    def __init__(
        self, transaction: Transaction, review: api.review.Review, *, is_pending: bool
    ) -> None:
        super().__init__(transaction, review)
        self.is_pending = is_pending

    @staticmethod
    def make(
        transaction: Transaction,
        review: api.review.Review,
        old_upstream: Optional[api.commit.Commit],
        new_upstream: Optional[api.commit.Commit],
        branch: Optional[api.branch.Branch],
    ) -> CreatedRebase:
        return CreatedRebase(transaction, review, is_pending=True).insert(
            review=review,
            old_upstream=old_upstream,
            new_upstream=new_upstream,
            uid=transaction.critic.effective_user,
            branch=branch,
        )


class ModifyRebase(Modifier[api.log.rebase.Rebase, CreatedRebase]):
    def cancel(self) -> None:
        if not self.subject.is_pending:
            raise api.log.rebase.Error("Only pending rebases can be cancelled")

        self.transaction.items.append(Delete(self.subject))

    @staticmethod
    def create(
        transaction: Transaction,
        review: api.review.Review,
        old_upstream: Optional[api.commit.Commit],
        new_upstream: Optional[api.commit.Commit],
        branch: Optional[api.branch.Branch],
    ) -> ModifyRebase:
        return ModifyRebase(
            transaction,
            CreatedRebase.make(transaction, review, old_upstream, new_upstream, branch),
        )
