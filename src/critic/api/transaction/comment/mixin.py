from typing import Optional

from critic import api
from critic.reviewing.comment.propagate import PropagationResult
from ..modifier import Modifier
from .modify import ModifyComment


class ModifyReview(Modifier[api.review.Review]):
    async def createComment(
        self,
        comment_type: api.comment.CommentType,
        author: api.user.User,
        text: str,
        location: Optional[api.comment.Location] = None,
        propagation_result: Optional[PropagationResult] = None,
    ) -> ModifyComment:
        if self.subject.state == "draft":
            raise api.review.Error("Review has not been published")
        return await ModifyComment.create(
            self.transaction,
            self.subject,
            comment_type,
            author,
            text,
            location,
            propagation_result,
        )

    async def modifyComment(self, comment: api.comment.Comment) -> ModifyComment:
        if await comment.review != self.subject:
            raise api.review.Error("Cannot modify comment belonging to another review")

        # Users are not (generally) allowed to modify other users' draft
        # comments.
        if comment.is_draft:
            api.PermissionDenied.raiseUnlessUser(
                self.transaction.critic, await comment.author
            )

        return ModifyComment(self.transaction, comment)
