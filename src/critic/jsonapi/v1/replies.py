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

from typing import Sequence, Optional, Union, Set

from critic import api
from critic import jsonapi


class Replies(
    jsonapi.ResourceClass[api.reply.Reply],
    api_module=api.reply,
    exceptions=(api.comment.Error, api.reply.Error),
):
    """Replies to comments in reviews."""

    contexts = (None, "comments")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.reply.Reply
    ) -> jsonapi.JSONResult:
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
            "timestamp": jsonapi.v1.timestamp(value.timestamp),
            "text": value.text,
        }

    @staticmethod
    async def single(parameters: jsonapi.Parameters, argument: str) -> api.reply.Reply:
        """Retrieve one (or more) replies to comments.

           REPLY_ID : integer

           Retrieve a reply identified by its unique numeric id."""

        reply = await api.reply.fetch(
            parameters.critic, reply_id=jsonapi.numeric_id(argument)
        )

        comment = await Comments.deduce(parameters)
        if comment and comment != reply.comment:
            raise jsonapi.PathError("Reply does not belong to specified comment")

        return reply

    @staticmethod
    async def multiple(parameters: jsonapi.Parameters) -> Sequence[api.reply.Reply]:
        """Retrieve replies to a comment.

           comment : COMMENT_ID : integer

           Retrieve all replies to the specified comment."""

        comment = await Comments.deduce(parameters)

        if not comment:
            raise jsonapi.UsageError("A comment must be identified.")

        return await comment.replies

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.reply.Reply:
        critic = parameters.critic

        converted = await jsonapi.convert(
            parameters,
            {"comment?": api.comment.Comment, "author?": api.user.User, "text?": str},
            data,
        )

        comment = await Comments.deduce(parameters)

        if not comment:
            if "comment" not in converted:
                raise jsonapi.UsageError("No comment specified")
            comment = converted["comment"]
        elif "comment" in converted and comment != converted["comment"]:
            raise jsonapi.UsageError("Conflicting comments specified")
        assert comment

        if "author" in converted:
            author = converted["author"]
        else:
            author = critic.actual_user
        assert author

        review = await comment.review

        async with api.transaction.start(critic) as transaction:
            modifier = await transaction.modifyReview(review).modifyComment(comment)
            reply = await modifier.addReply(
                author=author, text=converted.get("text", "")
            )

        await jsonapi.v1.batches.includeUnpublished(parameters, review)

        return await reply

    @staticmethod
    async def update(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.reply.Reply],
        data: jsonapi.JSONInput,
    ) -> None:
        critic = parameters.critic

        converted = await jsonapi.convert(parameters, {"text": str}, data)

        async with api.transaction.start(critic) as transaction:
            for reply in values:
                comment = await reply.comment
                comment_modifier = await transaction.modifyReview(
                    await comment.review
                ).modifyComment(comment)
                modifier = await comment_modifier.modifyReply(reply)
                await modifier.setText(converted["text"])

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[api.reply.Reply]
    ) -> None:
        critic = parameters.critic

        reviews: Set[api.review.Review] = set()
        comments: Set[api.comment.Comment] = set()

        async with api.transaction.start(critic) as transaction:
            for reply in values:
                comment = await reply.comment
                comments.add(comment)
                review = await comment.review
                reviews.add(review)

                review_modifier = transaction.modifyReview(review)
                comment_modifier = await review_modifier.modifyComment(comment)
                reply_modifier = await comment_modifier.modifyReply(reply)
                reply_modifier.delete()

        if len(reviews) == 1:
            await jsonapi.v1.batches.includeUnpublished(parameters, reviews.pop())

        if "comments" in parameters.include:
            for comment in comments:
                parameters.addLinked(comment)

    @staticmethod
    async def fromParameterValue(
        parameters: jsonapi.Parameters, value: str
    ) -> api.reply.Reply:
        return await api.reply.fetch(parameters.critic, jsonapi.numeric_id(value))


from .comments import Comments
