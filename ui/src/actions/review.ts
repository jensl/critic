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

import { assertNotReached } from "../debug"
import { RequestParams, ExcludeFields, HandleError } from "../utils/Fetch.types"
import {
  RequestOptions,
  fetch,
  fetchOne,
  deleteResource,
  updateResource,
  createResource,
} from "../resources"
import { showToast } from "./uiToast"
import { AsyncThunk, Dispatch } from "../state"
import { ReviewID, UserID, RepositoryID, CommitID } from "../resources/types"
import Review from "../resources/review"
import { SessionID } from "../utils/SessionContext"
import {
  ReviewCategory,
  UpdateReviewCategoryAction,
  UPDATE_REVIEW_CATEGORY,
} from "."
import { ResourceData } from "../types"

export const updateReviewCategory = (
  category: ReviewCategory,
  reviewIDs: Iterable<ReviewID>
): UpdateReviewCategoryAction => ({
  type: UPDATE_REVIEW_CATEGORY,
  category,
  reviewIDs: [...reviewIDs],
})

export const createReview = (repository: RepositoryID, commits: CommitID[]) =>
  createResource("reviews", { repository, commits })

export const deleteReview = (reviewID: ReviewID) =>
  deleteResource("reviews", reviewID)

const updateReview = (
  reviewID: ReviewID,
  updates: ResourceData,
  options?: RequestOptions
) => updateResource("reviews", reviewID, updates, options)

const setReviewState = (state: ReviewState) => (reviewID: ReviewID) =>
  updateReview(reviewID, { state })

export const closeReview = setReviewState("closed")
export const dropReview = setReviewState("dropped")
export const reopenReview = setReviewState("open")

export const publishReview = (reviewID: ReviewID) => async (
  dispatch: Dispatch
) => {
  await setReviewState("open")
  dispatch(showToast({ type: "success", title: "Review published!" }))
}

export type ReviewState = "draft" | "open" | "closed" | "dropped"
export const setSummary = (reviewID: ReviewID, summary: string) =>
  updateReview(reviewID, { summary })

export const setOwners = (reviewID: ReviewID, owners: UserID[]) =>
  updateReview(reviewID, { owners })

export const setBranch = (
  reviewID: ReviewID,
  branch: string,
  handleError?: HandleError
) => updateReview(reviewID, { branch }, { include: ["branches"], handleError })

export const loadReview = (reviewID: ReviewID) => async (
  dispatch: Dispatch
) => {
  const { limited } = await dispatch(fetch("reviews", reviewID))
  if (!limited) return
  if (limited.has("changesets") || limited.has("reviewablefilechanges")) {
    const params: RequestParams = { fields: "changesets" }
    const excludeFields: ExcludeFields = {}
    if (!limited.has("changesets")) {
      // If we've got all changesets already, we just want the reviewable file
      // changes for each changeset.
      params["fields[changesets]"] = "review_state.reviewablefilechanges"
    } else {
      excludeFields.changesets = [
        "completion_level",
        "contributing_commits",
        "review_state.comments",
      ]
    }
    await dispatch(
      fetchOne("reviews", reviewID, {
        params,
        excludeFields,
        include: ["changesets", "reviewablefilechanges", "files"],
      })
    )
  }
}

export const loadReviewCategory = (
  category: ReviewCategory,
  // This fetch implicitly depends on the signed in user.
  _: SessionID
): AsyncThunk<void> => async (dispatch) => {
  const params: RequestParams = {
    fields: [
      "id",
      "state",
      "last_changed",
      "owners",
      "progress.reviewing",
      "progress.open_issues",
      "summary",
      "tags",
      "branch",
    ].join(","),
    output_format: "static",
  }
  switch (category) {
    case "incoming":
    case "outgoing":
    case "other":
      params.category = category
      break

    case "open":
    case "closed":
      params.state = category
      break

    default:
      assertNotReached()
  }
  const { primary } = await dispatch(
    fetch("reviews", { params, include: ["reviewtags", "users"] })
  )
  if (!primary) return
  dispatch(
    updateReviewCategory(
      category,
      primary.map((review: Review) => review.id)
    )
  )
}

export type ReviewAction = UpdateReviewCategoryAction
