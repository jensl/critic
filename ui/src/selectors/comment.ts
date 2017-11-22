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

import { castImmutable } from "immer"
import { createSelector } from "reselect"

import { State } from "../state"
import Comment from "../resources/comment"
import Reply from "../resources/reply"
import { CommentID } from "../resources/types"

const getReplies = (state: State) => state.resource.replies

type CommentProp = { comment: Comment | null }
type CommentIDProp = { commentID: CommentID }
type GetCommentProps = CommentProp | CommentIDProp

const isCommentProp = (props: GetCommentProps): props is CommentProp =>
  "comment" in props

export const getComment = (state: State, props: GetCommentProps) =>
  isCommentProp(props)
    ? props.comment
    : state.resource.comments.get(props.commentID)

export const getRepliesPerComment = createSelector(getReplies, (replies) => {
  const result = new Map<CommentID, Set<Reply>>()
  for (const reply of replies.values()) {
    let perComment = result.get(reply.comment)
    if (!perComment) result.set(reply.comment, (perComment = new Set<Reply>()))
    perComment.add(reply)
  }
  return castImmutable(result)
})

export const getRepliesForComment = createSelector(
  getRepliesPerComment,
  getComment,
  (repliesPerComment, comment) =>
    (comment && repliesPerComment.get(comment.id)) || new Set()
)
