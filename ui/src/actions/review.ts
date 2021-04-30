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
import {
  RequestOptions,
  fetch,
  fetchOne,
  deleteResource,
  updateResource,
  createResource,
  withArgument,
  include,
  includeFields,
  excludeFields,
  withParameters,
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
import { disableDefaults } from "../resources/requestoptions"
import Repository from "../components/Repository"

export const updateReviewCategory = (
  category: ReviewCategory,
  reviewIDs: Iterable<ReviewID>,
): UpdateReviewCategoryAction => ({
  type: UPDATE_REVIEW_CATEGORY,
  category,
  reviewIDs: [...reviewIDs],
})

export const createReview = (
  repository: RepositoryID,
  commits: readonly CommitID[],
  summary: string = "",
) => createResource("reviews", { repository, commits, summary })

export const deleteReview = (reviewID: ReviewID) =>
  deleteResource("reviews", withArgument(reviewID))

const updateReview = (
  reviewID: ReviewID,
  updates: ResourceData,
  ...options: RequestOptions[]
) => updateResource("reviews", updates, withArgument(reviewID), ...options)

const setReviewState = (state: ReviewState) => (reviewID: ReviewID) =>
  updateReview(reviewID, { state })

export const closeReview = setReviewState("closed")
export const dropReview = setReviewState("dropped")
export const reopenReview = setReviewState("open")

export const publishReview = (reviewID: ReviewID) => async (
  dispatch: Dispatch,
) => {
  await dispatch(setReviewState("open")(reviewID))
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
  ...options: RequestOptions[]
) => updateReview(reviewID, { branch }, include("branches"), ...options)

export const loadReview = (reviewID: ReviewID): AsyncThunk<Review> => async (
  dispatch,
) => {
  const { primary, limited } = await dispatch(
    fetch("reviews", withArgument(reviewID)),
  )
  if (
    limited &&
    (limited.has("changesets") || limited.has("reviewablefilechanges"))
  ) {
    const options: RequestOptions[] = []
    if (!limited.has("changesets")) {
      // If we've got all changesets already, we just want the reviewable file
      // changes for each changeset.
      options.push(
        includeFields("changesets", ["review_state.reviewablefilechanges"]),
      )
    } else {
      options.push(
        excludeFields("changesets", [
          "completion_level",
          "contributing_commits",
          "review_state.comments",
        ]),
      )
    }
    return await dispatch(
      fetchOne(
        "reviews",
        disableDefaults(),
        withArgument(reviewID),
        withParameters({ fields: "changesets" }),
        include("changesets", "reviewablefilechanges", "files"),
        ...options,
      ),
    )
  }
  return primary[0]
}

const listOptions: RequestOptions[] = [
  include("reviewtags", "users"),
  includeFields("reviews", [
    "id",
    "state",
    "last_changed",
    "owners",
    "progress.reviewing",
    "progress.open_issues",
    "summary",
    "tags",
    "branch",
  ]),
]

export const loadReviewCategory = (
  category: ReviewCategory,
  // This fetch implicitly depends on the signed in user.
  _: SessionID,
): AsyncThunk<void> => async (dispatch) => {
  const options: RequestOptions[] = [...listOptions]
  switch (category) {
    case "incoming":
    case "outgoing":
    case "other":
      options.push(withParameters({ category }))
      break

    case "open":
    case "closed":
      options.push(withParameters({ state: category }))
      break

    default:
      assertNotReached()
  }
  const { primary } = await dispatch(fetch("reviews", ...options))
  if (!primary) return
  dispatch(
    updateReviewCategory(
      category,
      primary.map((review: Review) => review.id),
    ),
  )
}

export const loadRepositoryReviews = (
  repositoryID: RepositoryID,
  offset: number,
  count: number,
): AsyncThunk<Review[]> => async (dispatch) => {
  const options: RequestOptions[] = [...listOptions]
  options.push(withParameters({ repository: repositoryID, offset, count }))
  const { primary } = await dispatch(fetch("reviews", ...options))
  return primary
}

export type ReviewAction = UpdateReviewCategoryAction
