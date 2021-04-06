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

import Resource, { excludeFields, include, withParameters } from "../resources"
import { ReviewID } from "../resources/types"
import { AsyncThunk, Dispatch } from "../state"
import Batch from "../resources/batch"
import { DiscardItem } from "."

type BatchPayload = {
  review: ReviewID
  comment?: string
}

export const createBatch = (
  reviewID: ReviewID,
  comment?: string,
): AsyncThunk<Batch> => async (dispatch) => {
  const payload: BatchPayload = { review: reviewID }
  if (typeof comment === "string") {
    comment = comment.trim()
    if (comment.length > 0) payload.comment = comment
  }
  return await dispatch(
    Resource.create(
      "batches",
      payload,
      include(
        "reviews",
        "comments",
        "replies",
        "changesets",
        "reviewablefilechanges",
        "batches",
      ),
    ),
  )
}

export const discardUnpublishedChanges = (
  reviewID: ReviewID,
  items: DiscardItem[],
): AsyncThunk<void> => async (dispatch: Dispatch) => {
  const options = [
    include("batches"),
    include("reviews"),
    include("reviewtags"),
  ]
  if (
    items.includes("created_comments") ||
    items.includes("written_replies") ||
    items.includes("resolved_issues") ||
    items.includes("reopened_issues") ||
    items.includes("morphed_comments")
  ) {
    options.push(include("comments", "replies"))
    options.push(excludeFields("comments", ["location"]))
  }
  if (
    items.includes("reviewed_changes") ||
    items.includes("unreviewed_changes")
  ) {
    options.push(include("changesets", "reviewablefilechanges"))
    options.push(
      excludeFields("changesets", ["completion_level", "contributing_commits"]),
    )
    options.push(excludeFields("reviewablefilechanges", ["assigned_reviewers"]))
  }
  await dispatch(
    Resource.delete(
      "batches",
      withParameters({
        review: reviewID,
        unpublished: "yes",
        discard: items.join(","),
      }),
      ...options,
    ),
  )
}
