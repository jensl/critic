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

import logging
from typing import Collection, Optional
from critic import dbaccess

logger = logging.getLogger(__name__)

from critic import api
from critic.reviewing.comment.propagate import PropagationResult
from ..base import TransactionBase
from ..review import ReviewUser, ReviewUserTag
from ..item import Insert, InsertMany, Update
from ..createapiobject import CreateAPIObject


class CreateComment(CreateAPIObject[api.comment.Comment], api_module=api.comment):
    def __init__(self, transaction: TransactionBase, review: api.review.Review):
        super().__init__(transaction)
        self.review = review

    def scopes(self) -> Collection[str]:
        return (f"reviews/{self.review.id}",)

    @staticmethod
    async def make(
        transaction: TransactionBase,
        review: api.review.Review,
        comment_type: api.comment.CommentType,
        author: api.user.User,
        text: str,
        location: Optional[api.comment.Location],
        propagation_result: Optional[PropagationResult],
    ) -> api.comment.Comment:
        critic = transaction.critic

        # Users are not (generally) allowed to create comments as other users.
        api.PermissionDenied.raiseUnlessUser(critic, author)

        side = file = first_commit = last_commit = None

        if location:
            if location.type == "commit-message":
                first_commit = last_commit = await location.as_commit_message.commit
            elif location.type == "file-version":
                location = location.as_file_version
                side = location.side
                file = await location.file
                changeset = await location.changeset
                if changeset:
                    first_commit = await changeset.from_commit
                    last_commit = await changeset.to_commit
                else:
                    first_commit = last_commit = await location.commit

        comment = await CreateComment(transaction, review).insert(
            review=review,
            uid=author,
            type=comment_type,
            text=text,
            origin=side,
            file=file,
            first_commit=first_commit,
            last_commit=last_commit,
        )

        if location:
            transaction.tables.add("commentchainlines")
            if isinstance(location, api.comment.CommitMessageLocation):
                # FIXME: Make commit message comment line numbers one-based too!
                await transaction.execute(
                    Insert("commentchainlines").values(
                        chain=comment,
                        uid=author,
                        sha1=(await location.as_commit_message.commit).sha1,
                        first_line=location.first_line - 1,
                        last_line=location.last_line - 1,
                    )
                )
                # FIXME: ... and then delete the " - 1" from the above two lines.
            elif isinstance(location, api.comment.FileVersionLocation):
                assert propagation_result is not None
                await transaction.execute(
                    InsertMany(
                        "commentchainlines",
                        ["chain", "uid", "sha1", "first_line", "last_line"],
                        (
                            dbaccess.parameters(
                                chain=comment,
                                uid=author,
                                sha1=location.sha1,
                                first_line=location.first_line + 1,
                                last_line=location.last_line + 1,
                            )
                            for location in propagation_result.locations
                        ),
                    )
                )
                if comment_type == "issue" and propagation_result.addressed_by:
                    await transaction.execute(
                        Update(comment).set(
                            state="addressed",
                            addressed_by=propagation_result.addressed_by,
                        )
                    )

        ReviewUser.ensure(transaction, review, author)
        ReviewUserTag.ensure(transaction, review, author, "unpublished")

        return comment
