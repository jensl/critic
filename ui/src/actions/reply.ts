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

import Resource, { include, withArgument, withParameters } from "../resources"
import { CommentID, ReplyID } from "../resources/types"

const kIncludeResources = include("batches", "comments")

export const createReply = (commentID: CommentID) =>
  Resource.create(
    "replies",
    withParameters({ comment: commentID }),
    kIncludeResources,
  )

export const setReplyText = (replyID: ReplyID, text: string) =>
  Resource.update("replies", { text }, withArgument(replyID), kIncludeResources)

export const deleteReply = (replyID: ReplyID, callback = null) =>
  Resource.delete("replies", withArgument(replyID), kIncludeResources)
