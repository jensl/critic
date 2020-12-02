from __future__ import annotations

from critic import api
from ..item import Update
from ..modifier import Modifier
from . import StepsTaken


class ModifyReviewIntegrationRequest(
    Modifier[api.reviewintegrationrequest.ReviewIntegrationRequest]
):
    async def recordBranchUpdate(
        self, branchupdate: api.branchupdate.BranchUpdate, steps_taken: StepsTaken
    ) -> ModifyReviewIntegrationRequest:
        await self.transaction.execute(
            Update(self.subject)
            .set(branchupdate=branchupdate)
            .set_if(
                squashed=steps_taken.squashed,
                autosquashed=steps_taken.autosquashed,
                strategy_used=steps_taken.strategy_used,
            )
        )
        return self

    async def recordSuccess(self) -> ModifyReviewIntegrationRequest:
        await self.transaction.execute(Update(self.subject).set(successful=True))
        return self

    async def recordFailure(
        self, steps_taken: StepsTaken, error_message: str
    ) -> ModifyReviewIntegrationRequest:
        await self.transaction.execute(
            Update(self.subject)
            .set_if(
                squashed=steps_taken.squashed,
                autosquashed=steps_taken.autosquashed,
                strategy_used=steps_taken.strategy_used,
            )
            .set(
                successful=False,
                error_message=error_message,
            )
        )
        return self
