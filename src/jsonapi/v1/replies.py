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

import api
import jsonapi

@jsonapi.PrimaryResource
class Replies(object):
    """Replies to comments in reviews."""

    name = "replies"
    contexts = (None, "comments")
    value_class = api.reply.Reply
    exceptions = (api.comment.CommentError, api.reply.ReplyError)

    @staticmethod
    def json(value, parameters):
        """{
             "id": integer,
             "is_draft": boolean,
             "author": integer,
             "timestamp": float,
             "text": string,
           }"""

        timestamp = jsonapi.v1.timestamp(value.timestamp)
        return parameters.filtered(
            "replies", { "id": value.id,
                         "is_draft": value.is_draft,
                         "author": value.author,
                         "timestamp": timestamp,
                         "text": value.text })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) replies to comments.

           REPLY_ID : integer

           Retrieve a reply identified by its unique numeric id."""

        reply = api.reply.fetch(
            parameters.critic, reply_id=jsonapi.numeric_id(argument))

        comment = jsonapi.deduce("v1/comments", parameters)
        if comment and comment != reply.comment:
            raise jsonapi.PathError(
                "Reply does not belong to specified comment")

        return reply

    @staticmethod
    def multiple(parameters):
        """Retrieve replies to a comment.

           comment : COMMENT_ID : integer

           Retrieve all replies to the specified comment."""

        comment = jsonapi.deduce("v1/comments", parameters)

        if not comment:
            raise jsonapi.UsageError("A comment must be identified.")

        return comment.replies

    @staticmethod
    def create(parameters, value, values, data):
        critic = parameters.critic
        user = parameters.context.get("users", critic.actual_user)

        if value or values:
            raise jsonapi.UsageError("Invalid POST request")

        converted = jsonapi.convert(
            parameters,
            {
                "comment?": api.comment.Comment,
                "author?": api.user.User,
                "text": str
            },
            data)

        comment = jsonapi.deduce("v1/comments", parameters)

        if not comment:
            if "comment" not in converted:
                raise jsonapi.UsageError("No comment specified")
            comment = converted["comment"]
        elif "comment" in converted and comment != converted["comment"]:
            raise jsonapi.UsageError("Conflicting comments specified")

        if "author" in converted:
            author = converted["author"]
        else:
            author = critic.actual_user

        if not converted["text"].strip():
            raise jsonapi.UsageError("Empty reply")

        result = []

        def collectReply(reply):
            assert isinstance(reply, api.reply.Reply)
            result.append(reply)

        with api.transaction.Transaction(critic) as transaction:
            transaction \
                .modifyReview(comment.review) \
                .modifyComment(comment) \
                .addReply(
                    author=author,
                    text=converted["text"],
                    callback=collectReply)

        assert len(result) == 1
        return result[0], None

    @staticmethod
    def update(parameters, value, values, data):
        critic = parameters.critic
        path = parameters.subresource_path

        if value:
            replies = [value]
        else:
            replies = values

        if path:
            raise jsonapi.UsageError("Invalid PUT request")

        converted = jsonapi.convert(
            parameters,
            {
                "text": str
            },
            data)

        with api.transaction.Transaction(critic) as transaction:
            for reply in replies:
                transaction \
                    .modifyReview(reply.comment.review) \
                    .modifyComment(reply.comment) \
                    .modifyReply(reply) \
                    .setText(converted["text"])

        return value, values

    @staticmethod
    def delete(parameters, value, values):
        critic = parameters.critic
        path = parameters.subresource_path

        if value:
            replies = [value]
        else:
            replies = values

        if path:
            raise jsonapi.UsageError("Invalid DELETE request")

        with api.transaction.Transaction(critic) as transaction:
            for reply in replies:
                transaction \
                    .modifyReview(reply.comment.review) \
                    .modifyComment(reply.comment) \
                    .modifyReply(reply) \
                    .delete()

    @staticmethod
    def fromParameter(value, parameters):
        return api.reply.fetch(parameters.critic, jsonapi.numeric_id(value))
