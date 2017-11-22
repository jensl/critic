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

import { createSelector } from "reselect"

import { sortedComments } from "../utils/Comment"
import { State } from "../state"
import Comment from "../resources/comment"
import Review from "../resources/review"
import ReviewFilter from "../resources/reviewfilter"
import { ReviewID, UserID } from "../resources/types"
import { castImmutable } from "immer"

const getReviews = (state: State) => state.resource.reviews
const getComments = (state: State) => state.resource.comments
const getReplies = (state: State) => state.resource.replies
const getRebases = (state: State) => state.resource.rebases
export const getReviewFilters = (state: State) => state.resource.reviewfilters

type ReviewProp = { review: Review | null }
type ReviewIDProp = { reviewID: ReviewID }
type GetReviewProps = ReviewProp | ReviewIDProp

const isReviewProp = (props: GetReviewProps): props is ReviewProp =>
  "review" in props

export const getReview = (state: State, props: GetReviewProps) =>
  isReviewProp(props)
    ? props.review
    : state.resource.reviews.get(props.reviewID)

export const getCommentsPerReview = createSelector(getComments, (comments) => {
  const result = new Map<number, Set<Comment>>()
  for (const comment of comments.values()) {
    const reviewID = comment.review
    let perReview = result.get(reviewID)
    if (!perReview) result.set(reviewID, (perReview = new Set()))
    perReview.add(comment)
  }
  return castImmutable(result)
})

export const getCommentsForReview = createSelector(
  getCommentsPerReview,
  getReplies,
  getReview,
  (commentsPerReview, repliesByID, review): readonly Comment[] =>
    review
      ? sortedComments(commentsPerReview.get(review.id) || [], repliesByID)
      : []
)

export const getIssuesForReview = createSelector(
  getCommentsForReview,
  (comments): readonly Comment[] =>
    comments.filter((comment) => comment.type === "issue")
)

export const getOpenIssuesForReview = createSelector(
  getIssuesForReview,
  (issues): readonly Comment[] =>
    issues.filter((issue) => issue.state === "open")
)

export const getResolvedIssuesForReview = createSelector(
  getIssuesForReview,
  (issues): readonly Comment[] =>
    issues.filter((issue) => issue.state === "resolved")
)

export const getAddressedIssuesForReview = createSelector(
  getIssuesForReview,
  (issues): readonly Comment[] =>
    issues.filter((issue) => issue.state === "addressed")
)

export const getNotesForReview = createSelector(
  getCommentsForReview,
  (comments): readonly Comment[] =>
    comments.filter((comment) => comment.type === "note")
)

export const getPendingRebase = createSelector(
  getRebases,
  getReview,
  (rebases, review) =>
    typeof review?.pendingRebase === "number"
      ? rebases.get(review.pendingRebase)
      : null
)

export const getReviewFiltersPerReview = createSelector(
  getReviewFilters,
  (reviewFilters) => {
    const result = new Map<number, Set<ReviewFilter>>()
    reviewFilters.forEach((reviewFilter) => {
      const perReview = result.get(reviewFilter.review)
      if (perReview) perReview.add(reviewFilter)
      else result.set(reviewFilter.review, new Set([reviewFilter]))
    })
    return castImmutable(result)
  }
)

export const getReviewFiltersForReview = createSelector(
  getReviewFiltersPerReview,
  getReview,
  (reviewFilters, review) => (review ? reviewFilters.get(review.id) : null)
)

export const getRelevantReviewersPerReview = createSelector(
  getReviews,
  getReviewFiltersPerReview,
  (reviews, reviewFiltersPerReview) => {
    const relevantReviewers = new Map<ReviewID, Set<UserID>>()
    const perReview = (review: Review) => {
      var reviewerIDs = relevantReviewers.get(review.id)
      if (!reviewerIDs)
        relevantReviewers.set(review.id, (reviewerIDs = new Set()))
      return reviewerIDs
    }
    for (const review of reviews.values()) {
      const reviewerIDs = perReview(review)
      // All active reviewers are relevant.
      review.activeReviewers.forEach((reviewerID) =>
        reviewerIDs.add(reviewerID)
      )
      // Also all reviewers added via review filters, as this indicates either
      // that they added themselves in this review specifically, or that their
      // reviewing was directly requested by someone, most likely the review
      // owner.
      const reviewFilters = reviewFiltersPerReview.get(review.id)
      if (reviewFilters)
        reviewFilters.forEach((reviewFilter) => {
          if (reviewFilter.type === "reviewer")
            reviewerIDs.add(reviewFilter.subject)
        })
    }
    return castImmutable(relevantReviewers)
  }
)
