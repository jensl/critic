from typing import Collection

from critic import api
from critic import dbaccess
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject
from ..item import Insert, InsertMany
from ..review.finalizeassignments import FinalizeAssignments
from ..review.reviewassignmentstransaction import ReviewAssignmentsTransaction
from ..review.updatereviewtags import UpdateReviewTags
from ..review import ReviewUser


class CreatedReviewFilter(
    CreateAPIObject[api.reviewfilter.ReviewFilter], api_module=api.reviewfilter
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        review: api.review.Review,
        subject: api.user.User,
        filter_type: api.reviewfilter.FilterType,
        path: str,
        default_scope: bool,
        scopes: Collection[api.reviewscope.ReviewScope],
    ) -> api.reviewfilter.ReviewFilter:
        reviewfilter = await CreatedReviewFilter(transaction).insert(
            review=review,
            uid=subject,
            type=filter_type,
            path=path,
            default_scope=default_scope,
            creator=transaction.critic.effective_user,
        )

        if scopes:
            await transaction.execute(
                InsertMany(
                    "reviewfilterscopes",
                    ["filter", "scope"],
                    (
                        dbaccess.parameters(filter=reviewfilter, scope=scope)
                        for scope in scopes
                    ),
                )
            )

        assignments_transaction = await ReviewAssignmentsTransaction.make(
            transaction, review
        )

        transaction.tables.add("reviewfilterchanges")
        await transaction.execute(
            Insert("reviewfilterchanges").values(
                transaction=assignments_transaction,
                uid=subject,
                type=filter_type,
                path=path,
                created=True,
            )
        )

        ReviewUser.ensure(transaction, review, subject)

        transaction.finalizers.add(
            FinalizeAssignments(assignments_transaction, subject)
        )
        transaction.finalizers.add(UpdateReviewTags(review))

        return reviewfilter
