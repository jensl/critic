from typing import Iterable, Optional

from critic import api
from ..base import TransactionBase
from .modify import ModifyReview


class Transaction(TransactionBase):
    async def createReview(
        self,
        repository: api.repository.Repository,
        owners: Iterable[api.user.User],
        *,
        head: Optional[api.commit.Commit] = None,
        commits: Optional[Iterable[api.commit.Commit]] = None,
        branch: Optional[api.branch.Branch] = None,
        target_branch: Optional[api.branch.Branch] = None,
        via_push: bool = False,
    ) -> ModifyReview:
        return await ModifyReview.create(
            self, repository, owners, head, commits, branch, target_branch, via_push
        )

    def modifyReview(self, subject: api.review.Review) -> ModifyReview:
        return ModifyReview(self, subject)
