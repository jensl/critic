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

import { getReview } from "./review"
import { getChangeset } from "./fileDiff"
import { State } from "../state"
import ReviewableFileChange from "../resources/reviewablefilechange"
import { ReviewID, CommitID, ChangesetID, FileID } from "../resources/types"

const getChangesets = (state: State) => state.resource.changesets
const getReviewableFileChanges = (state: State) =>
  state.resource.reviewablefilechanges

const getReviewableFileChangesAsArray = createSelector(
  getReviewableFileChanges,
  (reviewableFileChanges) => castImmutable([...reviewableFileChanges.values()])
)

export const getReviewableFileChangesForReview = createSelector(
  getReview,
  getReviewableFileChangesAsArray,
  (review, reviewableFileChanges) =>
    review
      ? reviewableFileChanges.filter((rfc) => rfc.review === review.id)
      : null
)

export const getReviewableFileChangesPerReviewAndCommit = createSelector(
  getChangesets,
  getReviewableFileChanges,
  (changesets, reviewableFileChanges) => {
    const result = new Map<ReviewID, Map<CommitID, Set<ReviewableFileChange>>>()
    for (const rfc of reviewableFileChanges.values()) {
      const changeset = changesets.byID.get(rfc.changeset)
      if (!changeset) {
        console.error({ rfc, changesets: changesets.byID })
        continue
      }
      const commitID = changeset.toCommit
      let perReview = result.get(rfc.review)
      let perCommit: Set<ReviewableFileChange> | undefined
      if (!perReview)
        result.set(
          rfc.review,
          (perReview = new Map([[commitID, (perCommit = new Set())]]))
        )
      else {
        perCommit = perReview.get(commitID)
        if (!perCommit) perReview.set(commitID, (perCommit = new Set()))
      }
      perCommit.add(rfc)
    }
    return castImmutable(result)
  }
)

export const getReviewableFileChangesPerChangeset = createSelector(
  getReviewableFileChangesForReview,
  (reviewableFileChanges) => {
    const result = new Map<ChangesetID, Set<ReviewableFileChange>>()
    if (reviewableFileChanges)
      for (const rfc of reviewableFileChanges) {
        let perChangeset = result.get(rfc.changeset)
        if (!perChangeset) result.set(rfc.changeset, (perChangeset = new Set()))
        perChangeset.add(rfc)
      }
    return castImmutable(result)
  }
)

export const getReviewableFileChangesForChangeset = createSelector(
  getChangesets,
  getReviewableFileChangesForReview,
  getChangeset,
  (changesets, reviewableFileChanges, changeset) => {
    if (
      !reviewableFileChanges ||
      !changeset ||
      !changeset.contributingCommits ||
      !changeset.files
    ) {
      return null
    }
    const result = new Map<FileID, Set<ReviewableFileChange>>()
    for (const fileID of changeset.files) result.set(fileID, new Set())
    let found = false
    if (changeset.contributingCommits.length === 1) {
      for (const rfc of reviewableFileChanges) {
        if (rfc.changeset === changeset.id) {
          result.get(rfc.file)!.add(rfc)
          found = true
        }
      }
    } else {
      const contributingChangesetIDs = new Set(
        changeset.contributingCommits.map((commitID) =>
          changesets.byCommits.get(String(commitID))
        )
      )
      for (const rfc of reviewableFileChanges) {
        if (contributingChangesetIDs.has(rfc.changeset)) {
          let perFile = result.get(rfc.file)
          if (!perFile) result.set(rfc.file, (perFile = new Set()))
          perFile.add(rfc)
          found = true
        }
      }
    }
    if (!found) return null
    return castImmutable(result)
  }
)
