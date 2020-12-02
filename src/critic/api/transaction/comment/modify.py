# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

from __future__ import annotations

import difflib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

from critic import api
from critic.reviewing.comment.propagate import PropagationResult
from ..review import ReviewUserTag, has_unpublished_changes
from ..base import TransactionBase
from ..item import Update
from ..modifier import Modifier
from ..reply.mixin import ModifyComment as ReplyMixin
from .create import CreateComment


def is_simple_edit(old_string: str, new_string: str) -> bool:
    sm = difflib.SequenceMatcher(None, old_string, new_string)
    matched = sum(length for _, _, length in sm.get_matching_blocks())
    return matched == len(old_string)


class ModifyComment(ReplyMixin, Modifier[api.comment.Comment]):
    def __init__(
        self,
        transaction: TransactionBase,
        comment: api.comment.Comment,
    ):
        super().__init__(transaction, comment)
        # transaction.lock("commentchains", id=self.subject.id)

    def __raiseUnlessDraft(self, action: str) -> None:
        if not self.subject.is_draft:
            raise api.comment.Error("Published comments cannot be " + action)

    async def setText(self, new_text: str) -> None:
        self.__raiseUnlessDraft("edited")

        # Definition:
        #   simple edit: the new value contains all characters from the old value in the
        #                same order (but with added extra characters somewhere.)
        # Policy:
        #   Save a backup unless either of these conditions are met:
        #   - the new text is a simple edit of the current text, or
        #   - the latest backup is a simple edit of the current text.
        # Meaning:
        #   We don't need to save a backup when adding some characters on top of the
        #   current value, and we also don't need to save a backup of the current text
        #   if it is just the latest backup minus some characters, as that means it
        #   came to be by simply deleting some characters.

        # save_backup = False
        # if isinstance(self.subject, api.comment.Comment) and not is_simple_edit(
        #     self.subject.text, new_text
        # ):
        #     draft_changes = await self.subject.draft_changes
        #     if draft_changes and draft_changes.text_backups:
        #         latest_backup = draft_changes.text_backups[0]
        #         if not is_simple_edit(self.subject.text, latest_backup.value):
        #             save_backup = True

        await self.transaction.execute(Update(self.subject).set(text=new_text))

        # if save_backup:
        #     self.transaction.items.append(
        #         Insert("commenttextbackups").values(
        #             uid=self.transaction.critic.effective_user,
        #             comment=self.subject,
        #             value=self.subject.text,
        #         )
        #     )

    async def resolveIssue(self) -> None:
        await resolve_issue(self.transaction, self.subject)

    async def reopenIssue(
        self, new_location: Optional[api.comment.Location] = None
    ) -> None:
        await reopen_issue(self.transaction, self.subject, new_location)

    async def deleteComment(self) -> None:
        self.__raiseUnlessDraft("deleted")

        critic = self.transaction.critic
        author = await self.subject.author

        api.PermissionDenied.raiseUnlessUser(critic, author)

        await super().delete()

        ReviewUserTag.ensure(
            self.transaction,
            await self.subject.review,
            author,
            "unpublished",
            has_unpublished_changes,
        )

    @staticmethod
    async def create(
        transaction: TransactionBase,
        review: api.review.Review,
        comment_type: api.comment.CommentType,
        author: api.user.User,
        text: str,
        location: Optional[api.comment.Location],
        propagation_result: Optional[PropagationResult],
    ) -> ModifyComment:
        return ModifyComment(
            transaction,
            await CreateComment.make(
                transaction,
                review,
                comment_type,
                author,
                text,
                location,
                propagation_result,
            ),
        )


from .resolveissue import resolve_issue
from .reopenissue import reopen_issue
