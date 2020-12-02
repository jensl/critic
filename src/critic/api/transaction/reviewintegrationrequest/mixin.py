from typing import Optional

from critic import api
from ..modifier import Modifier
from ..reviewintegrationrequest.modify import ModifyReviewIntegrationRequest
from .create import CreatedReviewIntegrationRequest


class ModifyReview(Modifier[api.review.Review]):
    async def requestIntegration(
        self,
        do_squash: bool,
        squash_message: Optional[str],
        do_autosquash: bool,
        do_integrate: bool,
    ) -> api.reviewintegrationrequest.ReviewIntegrationRequest:
        return await CreatedReviewIntegrationRequest.make(
            self.transaction,
            self.subject,
            do_squash,
            squash_message,
            do_autosquash,
            do_integrate,
        )

    async def modifyIntegrationRequest(
        self, request: api.reviewintegrationrequest.ReviewIntegrationRequest
    ) -> ModifyReviewIntegrationRequest:
        if self.subject != await request.review:
            raise api.review.Error(
                "Cannot modify integration request belonging to another review"
            )
        return ModifyReviewIntegrationRequest(self.transaction, request)
