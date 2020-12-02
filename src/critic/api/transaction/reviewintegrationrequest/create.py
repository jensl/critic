from typing import Optional

from critic import api
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject


class CreatedReviewIntegrationRequest(
    CreateAPIObject[api.reviewintegrationrequest.ReviewIntegrationRequest]
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        review: api.review.Review,
        do_squash: bool,
        squash_message: Optional[str],
        do_autosquash: bool,
        do_integrate: bool,
    ) -> api.reviewintegrationrequest.ReviewIntegrationRequest:
        integration = await review.integration
        assert integration
        target_branch = integration.target_branch
        review_branch = await review.branch
        assert review_branch
        branchupdate = (await review_branch.updates)[-1]

        return await CreatedReviewIntegrationRequest(transaction).insert(
            review=review,
            target=target_branch,
            branchupdate=branchupdate,
            do_squash=do_squash,
            squash_message=squash_message,
            do_autosquash=do_autosquash,
            do_integrate=do_integrate,
        )
