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
from typing import Optional

logger = logging.getLogger(__name__)

from . import CreatedComment
from ..review import ReviewUserTag
from .. import Transaction, Query, Insert, InsertMany

from critic import api
from critic import reviewing


async def create_comment(
    transaction: Transaction,
    review: api.review.Review,
    comment_type: api.comment.CommentType,
    author: api.user.User,
    text: str,
    location: Optional[api.comment.Location],
) -> CreatedComment:
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

    comment = CreatedComment(transaction, review, location).insert(
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
        if location.type == "commit-message":
            # FIXME: Make commit message comment line numbers one-based too!
            transaction.items.append(
                Insert("commentchainlines").values(
                    chain=comment,
                    uid=author,
                    sha1=(await location.as_commit_message.commit).sha1,
                    first_line=location.first_line - 1,
                    last_line=location.last_line - 1,
                )
            )
            # FIXME: ... and then delete the " - 1" from the above two lines.
        elif location.type == "file-version":
            result = await reviewing.comment.propagate.propagate_new_comment(
                review, location
            )
            transaction.items.append(
                InsertMany(
                    "commentchainlines",
                    ["chain", "uid", "sha1", "first_line", "last_line"],
                    (
                        dict(
                            chain=comment,
                            uid=author,
                            sha1=location.sha1,
                            first_line=location.first_line + 1,
                            last_line=location.last_line + 1,
                        )
                        for location in result.locations
                    ),
                )
            )
            if comment_type == "issue" and result.addressed_by:
                transaction.items.append(
                    Query(
                        """UPDATE commentchains
                              SET state='addressed',
                                  addressed_by={addressed_by}
                            WHERE id={comment}""",
                        addressed_by=result.addressed_by,
                        comment=comment,
                    )
                )
                comment.state = "addressed"

    ReviewUserTag.ensure(transaction, review, author, "unpublished")

    return comment
