from typing import Iterable, Optional

from critic import api
from .modify import ModifyBranch
from ..modifier import Modifier


class ModifyRepository(Modifier[api.repository.Repository]):
    async def createBranch(
        self,
        branch_type: api.branch.BranchType,
        name: str,
        commits: Iterable[api.commit.Commit],
        *,
        head: Optional[api.commit.Commit] = None,
        base_branch: Optional[api.branch.Branch] = None,
        output: Optional[str] = None,
        is_creating_review: bool = False,
        pendingrefupdate_id: Optional[int] = None,
    ) -> ModifyBranch:
        return await ModifyBranch.create(
            self.transaction,
            self.subject,
            branch_type,
            name,
            commits,
            head,
            base_branch,
            output,
            is_creating_review,
            pendingrefupdate_id,
        )

    async def modifyBranch(self, branch: api.branch.Branch) -> ModifyBranch:
        assert await branch.repository == self.subject
        return ModifyBranch(self.transaction, branch)
