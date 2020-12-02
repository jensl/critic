from critic import api
from ..modifier import Modifier
from ..review import ReviewUserTag
from .modify import ModifyReply


class ModifyComment(Modifier[api.comment.Comment]):
    async def addReply(self, author: api.user.User, text: str) -> ModifyReply:
        if self.subject.is_draft:
            raise api.comment.Error("Draft comments cannot be replied to")

        draft_changes = await self.subject.draft_changes

        if draft_changes and draft_changes.reply:
            raise api.comment.Error("Comment already has a draft reply")

        # Users are not (generally) allowed to create comments as other users.
        api.PermissionDenied.raiseUnlessUser(self.critic, author)

        reply = await ModifyReply.create(self.transaction, self.subject, author, text)

        ReviewUserTag.ensure(
            self.transaction, await self.subject.review, author, "unpublished"
        )

        return reply

    async def modifyReply(self, reply: api.reply.Reply) -> ModifyReply:
        if await reply.comment != self.subject:
            raise api.comment.Error("Cannot modify reply belonging to another comment")
        api.PermissionDenied.raiseUnlessUser(
            self.transaction.critic, await reply.author
        )
        return ModifyReply(self.transaction, reply)
