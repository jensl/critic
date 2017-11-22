/*
 * Copyright 2017 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import Resource, {
  fetch,
  include,
  withArgument,
  withParameters,
} from "../resources"
import {
  CommentID,
  CommentType,
  ReviewID,
  FileID,
  ChangesetID,
  DiffSide,
  CommentLocationType,
  IssueState,
} from "../resources/types"

export const loadComment = (commentID: CommentID) =>
  fetch("comments", withArgument(commentID))

const kIncludeResources = include("batches", "reviews", "reviewtags")

type CommentPayload = {
  review: ReviewID
  type: CommentType
  text: string
  location?: {
    first_line: number
    last_line: number
    changeset: ChangesetID
    file: FileID
    side: DiffSide
    type: CommentLocationType
  }
}

export type Location = {
  changesetID: ChangesetID
  fileID: FileID
  side: DiffSide
  firstLine: number
  lastLine: number
}

export const createComment = (
  reviewID: ReviewID,
  type: CommentType,
  text: string = "",
  location?: Location
) => {
  var payload: CommentPayload = { review: reviewID, type, text }
  if (location) {
    payload.location = {
      type: "file-version",
      changeset: location.changesetID,
      file: location.fileID,
      side: location.side,
      first_line: location.firstLine,
      last_line: location.lastLine,
    }
  }
  return Resource.create("comments", payload, kIncludeResources)
}

export const setCommentText = (commentID: CommentID, text: string) =>
  Resource.update(
    "comments",
    { text },
    withArgument(commentID),
    kIncludeResources
  )

export const deleteComment = (commentID: CommentID) =>
  Resource.delete("comments", withArgument(commentID), kIncludeResources)

const setIssueState = (commentID: CommentID, newState: IssueState) =>
  Resource.update(
    "comments",
    { draft_changes: { new_state: newState } },
    withArgument(commentID),
    kIncludeResources
  )

export const resolveIssue = (commentID: CommentID) =>
  setIssueState(commentID, "resolved")
export const reopenResolvedIssue = (commentID: CommentID) =>
  setIssueState(commentID, "open")

export const reopenAddressedIssue = (
  commentID: CommentID,
  location: Location
) =>
  Resource.update(
    "comments",
    {
      draft_changes: {
        new_state: "open",
        new_location: {
          type: "file-version",
          changeset: location.changesetID,
          file: location.fileID,
          side: location.side,
          first_line: location.firstLine,
          last_line: location.lastLine,
        },
      },
    },
    withArgument(commentID),
    withParameters({ changeset: location.changesetID }),
    kIncludeResources
  )
