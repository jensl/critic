from typing import Dict, Literal, Optional, overload

from critic import api
from critic import dbaccess
from ..item import Insert, Update
from ..modifier import Modifier
from ..review import CreateReviewEvent, raiseUnlessPublished
from .create import CreateRebase
from .modify import ModifyRebase
from .preparerebase import prepare_rebase


class ModifyReview(Modifier[api.review.Review]):
    @overload
    async def prepareRebase(
        self, *, new_upstream: str, branch: Optional[api.branch.Branch] = None
    ) -> ModifyRebase:
        ...

    @overload
    async def prepareRebase(
        self,
        *,
        history_rewrite: Literal[True],
        branch: Optional[api.branch.Branch] = None,
    ) -> ModifyRebase:
        ...

    async def prepareRebase(
        self,
        *,
        new_upstream: Optional[str] = None,
        history_rewrite: Optional[Literal[True]] = None,
        branch: Optional[api.branch.Branch] = None,
    ) -> ModifyRebase:
        raiseUnlessPublished(self.subject)
        return await prepare_rebase(
            self.transaction, self.subject, new_upstream, bool(history_rewrite), branch
        )

    def modifyRebase(self, rebase: api.rebase.Rebase) -> ModifyRebase:
        return ModifyRebase(self.transaction, rebase)

    async def finishRebase(
        self,
        rebase: api.rebase.Rebase,
        branchupdate: api.branchupdate.BranchUpdate,
        new_upstream: Optional[api.commit.Commit] = None,
        *,
        equivalent_merge: Optional[api.commit.Commit] = None,
        replayed_rebase: Optional[api.commit.Commit] = None,
    ) -> None:
        updates: Dict[str, dbaccess.Parameter] = {"branchupdate": branchupdate}

        if isinstance(rebase, api.rebase.HistoryRewrite):
            assert new_upstream is None
            assert equivalent_merge is None
            assert replayed_rebase is None
        else:
            assert isinstance(new_upstream, api.commit.Commit)
            updates["new_upstream"] = new_upstream
            assert equivalent_merge is None or replayed_rebase is None
            if equivalent_merge is not None:
                assert isinstance(equivalent_merge, api.commit.Commit)
                updates["equivalent_merge"] = equivalent_merge
            if replayed_rebase is not None:
                assert isinstance(replayed_rebase, api.commit.Commit)
                updates["replayed_rebase"] = replayed_rebase

        self.transaction.tables.add("reviewrebases")
        await self.transaction.execute(
            Update("reviewrebases").set(**updates).where(id=rebase)
        )

    async def recordRebase(
        self,
        branchupdate: api.branchupdate.BranchUpdate,
        *,
        old_upstream: Optional[api.commit.Commit] = None,
        new_upstream: Optional[api.commit.Commit] = None,
    ) -> api.rebase.Rebase:
        event = await CreateReviewEvent.ensure(
            self.transaction,
            self.subject,
            "branchupdate",
            user=api.user.system(self.transaction.critic),
        )

        await self.transaction.execute(
            Insert("reviewupdates").values(branchupdate=branchupdate, event=event)
        )

        return await CreateRebase(self.transaction, self.subject).insert(
            review=self.subject,
            branchupdate=branchupdate,
            old_upstream=old_upstream,
            new_upstream=new_upstream,
        )
