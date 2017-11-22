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

import Comment from "../resources/comment"
import Reply from "../resources/reply"
import { ReplyID } from "../resources/types"

export const sortedComments = (
  comments: Iterable<Comment>,
  replies: ReadonlyMap<ReplyID, Reply>
): Comment[] => {
  const timestamp = (comment: Comment) => {
    const lastReply = replies.get(comment.replies[comment.replies.length - 1])
    return lastReply?.timestamp ?? comment.timestamp
  }
  const result = [...comments]
  return result.sort((a, b) => {
    const aTimestamp = timestamp(a)
    const bTimestamp = timestamp(b)
    if (aTimestamp !== bTimestamp) return bTimestamp - aTimestamp
    return a.id - b.id
  })
}

export const commentIDFromHash = (hash: Map<string, string>) => {
  switch (true) {
    case hash.has("comment"):
      return hash.get("comment")
    case hash.has("issue"):
      return hash.get("issue")
    case hash.has("openIssue"):
      return hash.get("openIssue")
    case hash.has("addressedIssue"):
      return hash.get("addressedIssue")
    case hash.has("resolvedIssue"):
      return hash.get("resolvedIssue")
    case hash.has("note"):
      return hash.get("note")
    default:
      return null
  }
}
