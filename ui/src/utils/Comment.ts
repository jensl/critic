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

import { Location } from "../actions/comment"
import { assertNotNull } from "../debug"
import { SelectionScope } from "../reducers/uiSelectionScope"
import Comment from "../resources/comment"
import Reply from "../resources/reply"
import { DiffSide, FileID, ReplyID } from "../resources/types"
import { mappedSet } from "./Functions"

export const sortedComments = (
  comments: Iterable<Comment>,
  replies: ReadonlyMap<ReplyID, Reply>,
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

export const fileIDFromLineID = (lineID: string): FileID =>
  parseInt((/^f(\d+):/.exec(lineID) ?? ["", "-1"])[1], 10)

export const sideFromLineID = (lineID: string): DiffSide | null =>
  /^f\d+:o\d+$/.test(lineID) ? "old" : /^f\d+:n\d+$/.test(lineID) ? "new" : null

export const sideFromLineIDs = (lineIDs: ReadonlySet<string>): DiffSide => {
  const sides = mappedSet(lineIDs, sideFromLineID)
  if (sides.has("old") && !sides.has("new")) return "old"
  if (sides.has("new") && !sides.has("old")) return "new"
  return "new"
}

export const lineNumberFromLineID = (lineID: string, side: DiffSide): number =>
  parseInt(
    ((side === "old"
      ? /^f\d+:o(\d+)(?::n\d+)?$/
      : /^f\d+(?::o\d+)?:n(\d+)$/
    ).exec(lineID) ?? ["", "0"])[1],
    10,
  )

export const locationFromSelectionScope = ({
  firstSelectedID,
  lastSelectedID,
  selectedIDs,
}: SelectionScope): Omit<Location, "changesetID"> => {
  assertNotNull(firstSelectedID)
  assertNotNull(lastSelectedID)

  const fileID = fileIDFromLineID(firstSelectedID)
  const side =
    sideFromLineID(firstSelectedID) ??
    sideFromLineID(lastSelectedID) ??
    sideFromLineIDs(selectedIDs)
  const firstLine = lineNumberFromLineID(firstSelectedID, side)
  const lastLine = lineNumberFromLineID(lastSelectedID, side)

  return { fileID, side, firstLine, lastLine }
}
