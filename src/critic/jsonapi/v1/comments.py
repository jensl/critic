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

from typing import (
    Awaitable,
    FrozenSet,
    Literal,
    Mapping,
    Optional,
    Sequence,
    TypedDict,
    Union,
    cast,
    overload,
)

from critic import api

from ..check import TypeCheckerInputAtom, TypeCheckerInputItem2, convert
from ..exceptions import UsageError, PathError, InputError, ResourceSkipped
from ..parameters import Parameters
from ..resourceclass import ResourceClass
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values
from ..v1 import timestamp

LOCATION: Mapping[str, TypeCheckerInputAtom] = {
    # Note: "general" not included here; |location| should be
    #       omitted instead.
    "type": frozenset(["commit-message", "file-version"]),
    "first_line": int,
    "last_line": int,
    "commit?": api.commit.Commit,
    "file?": api.file.File,
    "changeset?": api.changeset.Changeset,
    "side?": frozenset(["old", "new"]),
}

DRAFT_CHANGES: Mapping[str, TypeCheckerInputItem2] = {
    "new_state?": frozenset(["open", "resolved"]),
    "new_location?": LOCATION,
}


class LocationBase(TypedDict):
    type: api.comment.LocationType
    first_line: int
    last_line: int


class CommitMessageLocation(LocationBase):
    commit: Awaitable[api.commit.Commit]


class FileVersionLocation(LocationBase):
    file: Awaitable[api.file.File]
    changeset: Awaitable[Optional[api.changeset.Changeset]]
    side: api.comment.Side
    commit: Awaitable[Optional[api.commit.Commit]]


Location = Union[CommitMessageLocation, FileVersionLocation]


class DraftChanges(TypedDict):
    author: api.user.User
    is_draft: bool
    reply: Optional[api.reply.Reply]
    new_type: Optional[api.comment.CommentType]
    new_state: Optional[api.comment.IssueState]
    new_location: Optional[Awaitable[Optional[Location]]]


async def reduce_location(
    location: Optional[api.comment.Location],
) -> Optional[Location]:
    if location is None:
        return None

    if location.type == "commit-message":
        commit_message_location = location.as_commit_message
        return {
            "type": commit_message_location.type,
            "first_line": commit_message_location.first_line,
            "last_line": commit_message_location.last_line,
            "commit": commit_message_location.commit,
        }
    else:
        file_version_location = location.as_file_version
        return {
            "type": file_version_location.type,
            "first_line": file_version_location.first_line,
            "last_line": file_version_location.last_line,
            "file": file_version_location.file,
            "changeset": file_version_location.changeset,
            "side": file_version_location.side,
            "commit": file_version_location.commit,
        }


async def reduce_main_location(value: api.comment.Comment) -> Optional[Location]:
    location = await value.location
    if location is None:
        return None
    return await reduce_location(location)


async def translate_and_reduce_location(
    main_location: Optional[api.comment.Location],
    changeset: Optional[api.changeset.Changeset],
    commit: Optional[api.commit.Commit],
) -> Optional[Location]:
    if main_location is None:
        return None
    if main_location.type == "file-version" and (changeset or commit):
        # if changeset and changeset == await main_location.changeset:
        #     return None
        # if commit and commit == await main_location.commit:
        #     return None
        main_location = main_location.as_file_version
        if changeset:
            translated_location = await main_location.translateTo(changeset=changeset)
        else:
            assert commit is not None
            translated_location = await main_location.translateTo(commit=commit)
        if not translated_location:
            raise ResourceSkipped("Comment not present in changeset/commit")
        return await reduce_location(translated_location)
    return None


class Comments(
    ResourceClass[api.comment.Comment],
    api_module=api.comment,
    exceptions=(api.comment.Error, api.reply.Error),
):
    """Issues and notes in reviews."""

    contexts = (None, "reviews")

    @staticmethod
    async def json(parameters: Parameters, value: api.comment.Comment) -> JSONResult:
        """{
             "id": integer,
             "type": "issue" or "note",
             "is_draft": boolean,
             "state": "open", "addressed" or "resolved" (null for notes),
             "review": integer,
             "author": integer,
             "location": Location or null,
             "resolved_by": integer, // user that resolved the issue
             "addressed_by": integer, // commit that addressed the issue
             "timestamp": float,
             "text": string,
             "replies": integer[],
             "draft_changes": DraftChanges or null,
           }

           Location {
             "type": "commit-message" or "file-version",
             "first_line": integer, // first commented line (one-based,
                                    // inclusive)
             "last_line": integer, // last commented line (one-based, inclusive)
           }

           CommitMessageLocation : Location {
             "commit": integer // commented commit
           }

           FileVersionLocation : Location {
             "file": integer, // commented file
             "changeset": integer or null, // commented changeset
             "commit": integer, // commented commit
           }

           DraftChanges {
             "author": integer, // author of these draft changes
             "is_draft": boolean, // true if comment itself is unpublished
             "reply": integer or null, // unpublished reply
             "new_type": "issue" or "note", // unpublished comment type change
             "new_state": "open", "addressed" or "resolved" (null for notes)
             "new_location": FileVersionLocation or null,
           }"""

        changeset = await Changesets.deduce(parameters)
        # FileVersionLocation.translateTo() only allows one, so let
        # a deduced changeset win over a deduced commit.
        commit = await Commits.deduce(parameters) if changeset is None else None

        # If the comment's location needs to be translated, we need to do it
        # immediately, since doing so may raise ResourceSkipped as
        # a side-effect.
        translated_location: Optional[Location]
        if changeset or commit:
            main_location = await value.location
            translated_location = await translate_and_reduce_location(
                main_location, changeset, commit
            )
            location = reduce_location(main_location)
        else:
            location = reduce_main_location(value)
            translated_location = None

        result: JSONResult = {
            "id": value.id,
            "type": value.type,
            "is_draft": value.is_draft,
            "state": None,
            "review": value.review,
            "author": value.author,
            "location": location,
            "translated_location": translated_location,
            "resolved_by": None,
            "addressed_by": None,
            "timestamp": timestamp(value.timestamp),
            "text": value.text,
            "replies": value.replies,
            "draft_changes": None,
        }

        if isinstance(value, api.comment.Issue):
            result["state"] = value.state
            result["resolved_by"] = value.resolved_by
            result["addressed_by"] = value.addressed_by

        draft_changes = await value.draft_changes
        if draft_changes:
            draft_changes_json: DraftChanges = {
                "author": draft_changes.author,
                "is_draft": draft_changes.is_draft,
                "reply": draft_changes.reply,
                "new_type": draft_changes.new_type,
                "new_state": None,
                "new_location": None,
            }

            if isinstance(value, api.comment.Issue):
                draft_changes = cast(api.comment.Issue.DraftChanges, draft_changes)
                draft_changes_json.update(
                    {
                        "new_state": draft_changes.new_state,
                        "new_location": reduce_location(draft_changes.new_location),
                    }
                )

            result["draft_changes"] = draft_changes_json

        return result

    @staticmethod
    async def single(parameters: Parameters, argument: str) -> api.comment.Comment:
        """Retrieve one (or more) comments in reviews.

           COMMENT_ID : integer

           Retrieve a comment identified by its unique numeric id."""

        comment = await api.comment.fetch(
            parameters.critic, comment_id=numeric_id(argument)
        )

        review = await Reviews.deduce(parameters)
        if review and review != comment.review:
            raise PathError("Comment does not belong to specified review")

        return comment

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Union[api.comment.Comment, Sequence[api.comment.Comment]]:
        """Retrieve all comments in the system (or review.)

           with_reply : REPLY_ID : integer

           Retrieve only the comment to which the specified reply is a reply.
           This is equivalent to accessing /api/v1/comments/COMMENT_ID with that
           comment's numeric id.  When used, any other parameters are ignored.

           review : REVIEW_ID : integer

           Retrieve only comments in the specified review.  Can only be used if
           a review is not specified in the resource path.

           author : AUTHOR : integer or string

           Retrieve only comments authored by the specified user, identified by
           the user's unique numeric id or user name.

           comment_type : TYPE : -

           Retrieve only comments of the specified type.  Valid values are:
           <code>issue</code> and <code>note</code>.

           state : STATE : -

           Retrieve only issues in the specified state.  Valid values are:
           <code>open</code>, <code>addressed</code> and <code>resolved</code>.

           location_type : LOCATION : -

           Retrieve only comments in the specified type of location.  Valid
           values are: <code>general</code>, <code>commit-message</code> and
           <code>file-version</code>.

           changeset : CHANGESET_ID : integer

           Retrieve only comments visible in the specified changeset. Can not be
           combined with the <code>commit</code> parameter.

           commit : COMMIT : integer or string

           Retrieve only comments visible in the specified commit, either in its
           commit message or in the commit's version of a file. Combine with the
           <code>location_type</code> parameter to select only one of those
           possibilities. Can not be combined with the <code>changeset</code>
           parameter."""

        critic = parameters.critic

        reply = await Replies.fromParameter(parameters, "with_reply")
        if reply:
            return await reply.comment

        review = await Reviews.deduce(parameters)
        author = await Users.fromParameter(parameters, "author")

        comment_type = parameters.getQueryParameter(
            "comment_type", converter=api.comment.as_comment_type
        )
        state = parameters.getQueryParameter(
            "state", converter=api.comment.as_issue_state
        )
        location_type = parameters.getQueryParameter(
            "location_type", converter=api.comment.as_location_type,
        )

        changeset = await Changesets.deduce(parameters)
        commit = await Commits.deduce(parameters)

        if changeset and commit:
            raise UsageError("Incompatible parameters: changeset and commit")

        return await api.comment.fetchAll(
            critic,
            review=review,
            author=author,
            comment_type=comment_type,
            state=state,
            location_type=location_type,
            changeset=changeset,
            commit=commit,
        )

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> api.comment.Comment:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {
                "type": api.comment.COMMENT_TYPE_VALUES,
                "review!?": api.review.Review,
                "author?": api.user.User,
                "location?": LOCATION,
                "text": str,
            },
            data,
        )

        review = await Reviews.deduce(parameters)

        if not review:
            if "review" not in converted:
                raise UsageError("No review specified")
            review = converted["review"]
        elif "review" in converted and review != converted["review"]:
            raise UsageError("Conflicting reviews specified")
        assert review is not None

        if "author" in converted:
            author = converted["author"]
        else:
            author = critic.actual_user

        location = await Comments.locationFromInput(
            parameters, converted.get("location"), "location"
        )

        async with api.transaction.start(critic) as transaction:
            created_comment = await transaction.modifyReview(review).createComment(
                comment_type=converted["type"],
                author=author,
                text=converted["text"],
                location=location,
            )

        await includeUnpublished(parameters, review)

        return await created_comment

    @staticmethod
    async def update(
        parameters: Parameters, values: Values[api.comment.Comment], data: JSONInput,
    ) -> None:
        critic = parameters.critic

        converted = await convert(
            parameters, {"text?": str, "draft_changes?": DRAFT_CHANGES}, data,
        )

        if "draft_changes" in converted:
            new_location = await Comments.locationFromInput(
                parameters,
                converted["draft_changes"].get("new_location"),
                "draft_changes.new_location",
            )
        else:
            new_location = None

        async with api.transaction.start(critic) as transaction:
            for comment in values:
                modifier = await transaction.modifyReview(
                    await comment.review
                ).modifyComment(comment)

                if "text" in converted:
                    await modifier.setText(converted["text"])

                draft_changes = converted.get("draft_changes")
                if draft_changes:
                    if draft_changes.get("new_state") == "resolved":
                        await modifier.resolveIssue()
                    elif draft_changes.get("new_state") == "open":
                        if comment.as_issue.state == "addressed" and not new_location:
                            raise UsageError(
                                "data.draft_changes: new_location is required "
                                "when reopening addressed issue"
                            )
                        await modifier.reopenIssue(new_location)

    @staticmethod
    async def delete(
        parameters: Parameters, values: Values[api.comment.Comment]
    ) -> None:
        critic = parameters.critic
        reviews = set()

        async with api.transaction.start(critic) as transaction:
            for comment in values:
                review = await comment.review
                reviews.add(review)
                modifier = await transaction.modifyReview(review).modifyComment(comment)
                await modifier.deleteComment()

        if len(reviews) == 1:
            await includeUnpublished(parameters, reviews.pop())

    @overload
    @staticmethod
    async def deduce(parameters: Parameters,) -> Optional[api.comment.Comment]:
        ...

    @overload
    @staticmethod
    async def deduce(
        parameters: Parameters, *, required: Literal[True]
    ) -> api.comment.Comment:
        ...

    @staticmethod
    async def deduce(
        parameters: Parameters, *, required: bool = False
    ) -> Optional[api.comment.Comment]:
        comment = parameters.context.get("comments")
        comment_parameter = parameters.getQueryParameter("comment")
        if comment_parameter is not None:
            if comment is not None:
                raise UsageError(
                    "Redundant query parameter: comment=%s" % comment_parameter
                )
            comment = await api.comment.fetch(
                parameters.critic, comment_id=numeric_id(comment_parameter)
            )
        if required and not comment:
            raise UsageError.missingParameter("comment")
        return comment

    @staticmethod
    async def setAsContext(
        parameters: Parameters, comment: api.comment.Comment
    ) -> None:
        parameters.setContext(Comments.name, comment)
        # Also set the comment's review as context.
        await Reviews.setAsContext(parameters, await comment.review)

    @staticmethod
    async def locationFromInput(
        parameters: Parameters,
        location_input: Optional[JSONInput],
        key: str = "location",
    ) -> Optional[api.comment.Location]:
        if location_input is None:
            return None

        critic = parameters.critic

        location_type = location_input.pop("type")
        if location_type == "commit-message":
            required_fields = {"first_line", "last_line", "commit"}
            optional_fields = set()
        else:
            required_fields = {"first_line", "last_line", "file"}
            optional_fields = {"commit", "changeset", "side"}
        accepted_fields = required_fields | optional_fields

        for required_field in required_fields:
            if required_field not in location_input:
                raise InputError(f"data.{key}.{required_field}: missing attribute")
        for actual_field in location_input.keys():
            if actual_field not in accepted_fields:
                raise InputError(f"data.{key}.{actual_field}: unexpected attribute")

        side: Optional[Literal["old", "new"]] = None

        if location_type == "file-version":
            if "commit" in location_input:
                if "changeset" in location_input:
                    raise InputError(
                        f"data.{key}: only one of commit and changeset can be specified"
                    )
                changeset = None
                side = None
                commit = location_input["commit"]
            elif "changeset" not in location_input:
                raise InputError(
                    "data.%s: one of commit and changeset must be specified" % key
                )
            elif "side" not in location_input:
                raise InputError(
                    f"data.{key}.side: missing attribute (required when changeset is "
                    "specified)"
                )
            else:
                changeset = location_input["changeset"]
                if location_input["side"] not in ("old", "new"):
                    raise InputError(
                        f"data.{key}.side: invalid attribute value (must be either 'old' "
                        "or 'new')"
                    )
                side = location_input["side"]
                commit = None

        first_line = location_input["first_line"]
        assert isinstance(first_line, int)
        last_line = location_input["last_line"]
        assert isinstance(last_line, int)
        commit = location_input.get("commit")
        assert commit is None or isinstance(commit, api.commit.Commit)

        if location_type == "commit-message":
            assert commit is not None
            return api.comment.CommitMessageLocation.make(
                critic, first_line, last_line, commit
            )

        file = location_input["file"]
        assert isinstance(file, api.file.File)
        changeset = location_input.get("changeset")
        assert changeset is None or isinstance(changeset, api.changeset.Changeset)

        return await api.comment.FileVersionLocation.make(
            critic, first_line, last_line, file, changeset, side, commit
        )


from .batches import includeUnpublished
from .changesets import Changesets
from .commits import Commits
from .replies import Replies
from .reviews import Reviews
from .users import Users
