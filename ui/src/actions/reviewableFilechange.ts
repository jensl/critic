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

import { updateResources, RequestOptions } from "../resources"
import ReviewableFileChange from "../resources/reviewablefilechange"
import { ReviewID, ChangesetID, FileID } from "../resources/types"
import { AsyncThunk } from "../state"
import { RequestParams } from "../utils/Fetch.types"

export const toggleReviewableFileChange = (
  newReviewed: boolean,
  {
    reviewableFileChanges = null,
    reviewID = null,
    changesetID = null,
    fileID = null,
  }: {
    reviewableFileChanges?: ReviewableFileChange[] | null
    reviewID?: ReviewID | null
    changesetID?: ChangesetID | null
    fileID?: FileID | null
  }
): AsyncThunk<boolean> => async (dispatch, getState) => {
  const state = getState()
  const userID = state.resource.sessions.get("current")?.user || null

  if (!userID) return false

  const params: RequestParams = {}
  const options: RequestOptions = { include: ["batches"] }

  if (reviewableFileChanges) {
    const isAssigned = (rfc: ReviewableFileChange) =>
      rfc.assignedReviewers.has(userID)
    const isReviewed = (rfc: ReviewableFileChange) =>
      rfc.draftChanges ? rfc.draftChanges.newIsReviewed : rfc.isReviewed
    const shouldToggle = (rfc: ReviewableFileChange) =>
      newReviewed !== isReviewed(rfc)
    const rfcsToToggle = reviewableFileChanges
      .filter(isAssigned)
      .filter(shouldToggle)
    if (!rfcsToToggle.length) return false
    options.args = rfcsToToggle.map((rfc) => rfc.id)
  } else {
    Object.assign(params, {
      review: reviewID,
      changeset: changesetID,
      assignee: "(me)",
      state: newReviewed ? "pending" : "reviewed",
    })

    if (fileID !== null) params.file = fileID
  }

  const updated = await dispatch(
    updateResources(
      "reviewablefilechanges",
      params,
      {
        draft_changes: {
          new_is_reviewed: newReviewed,
        },
      },
      options
    )
  )

  return !!updated.length
}
