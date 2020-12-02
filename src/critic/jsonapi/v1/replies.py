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

from typing import Sequence, Set, Tuple

from critic import api
from critic.api.transaction.reply.modify import ModifyReply
from ..check import convert
from ..exceptions import PathError, UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values
from .timestamp import timestamp


async def modify(
    transaction: api.transaction.Transaction, reply: api.reply.Reply
) -> Tuple[api.review.Review, api.comment.Comment, ModifyReply]:
    comment = await reply.comment
    review = await comment.review

    review_modifier = transaction.modifyReview(review)
    comment_modifier = await review_modifier.modifyComment(comment)
    return review, comment, await comment_modifier.modifyReply(reply)


class Replies(
    ResourceClass[api.reply.Reply],
    api_module=api.reply,
    exceptions=(api.comment.Error, api.reply.Error),
):
    """Replies to comments in reviews."""

    contexts = (None, "comments")

    @staticmethod
    async def json(parameters: Parameters, value: api.reply.Reply) -> JSONResult:
        """{
          "id": integer,
          "is_draft": boolean,
          "author": integer,
          "timestamp": float,
          "text": string,
        }"""

        return {
            "id": value.id,
            "is_draft": value.is_draft,
            "comment": value.comment,
            "author": value.author,
            "timestamp": timestamp(value.timestamp),
            "text": value.text,
        }

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> api.reply.Reply:
        """Retrieve one (or more) replies to comments.

        REPLY_ID : integer

        Retrieve a reply identified by its unique numeric id."""

        reply = await api.reply.fetch(parameters.critic, reply_id=numeric_id(argument))

        comment = await parameters.deduce(api.comment.Comment)
        if comment and comment != reply.comment:
            raise PathError("Reply does not belong to specified comment")

        return reply

    @staticmethod
    async def multiple(parameters: Parameters) -> Sequence[api.reply.Reply]:
        """Retrieve replies to a comment.

        comment : COMMENT_ID : integer

        Retrieve all replies to the specified comment."""

        comment = await parameters.deduce(api.comment.Comment)

        if not comment:
            raise UsageError("A comment must be identified.")

        return await comment.replies

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> api.reply.Reply:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {
                "comment?": api.comment.Comment,
                "author?": api.user.User,  # type: ignore
                "text?": str,
            },
            data,
        )

        comment = await parameters.deduce(api.comment.Comment)

        if not comment:
            if "comment" not in converted:
                raise UsageError("No comment specified")
            comment = converted["comment"]
        elif "comment" in converted and comment != converted["comment"]:
            raise UsageError("Conflicting comments specified")
        assert comment

        if "author" in converted:
            author = converted["author"]
        else:
            author = critic.actual_user
        assert author

        review = await comment.review

        try:
            async with api.transaction.start(critic) as transaction:
                modifier = await transaction.modifyReview(review).modifyComment(comment)
                return (
                    await modifier.addReply(
                        author=author, text=converted.get("text", "")
                    )
                ).subject
        finally:
            await includeUnpublished(parameters, review)

    @classmethod
    async def update(
        cls,
        parameters: Parameters,
        values: Values[api.reply.Reply],
        data: JSONInput,
    ) -> None:
        critic = parameters.critic

        converted = await convert(parameters, {"text": str}, data)

        async with api.transaction.start(critic) as transaction:
            for reply in values:
                _, _, modifier = await modify(transaction, reply)
                await modifier.setText(converted["text"])

    @classmethod
    async def delete(
        cls, parameters: Parameters, values: Values[api.reply.Reply]
    ) -> None:
        critic = parameters.critic

        reviews: Set[api.review.Review] = set()
        comments: Set[api.comment.Comment] = set()

        async with api.transaction.start(critic) as transaction:
            for reply in values:
                review, comment, modifier = await modify(transaction, reply)

                comments.add(comment)
                reviews.add(review)

                await modifier.delete()

        if len(reviews) == 1:
            await includeUnpublished(parameters, reviews.pop())

        if "comments" in parameters.include:
            for comment in comments:
                parameters.addLinked(comment)

    @staticmethod
    async def fromParameterValue(parameters: Parameters, value: str) -> api.reply.Reply:
        return await api.reply.fetch(parameters.critic, numeric_id(value))


from .batches import includeUnpublished
