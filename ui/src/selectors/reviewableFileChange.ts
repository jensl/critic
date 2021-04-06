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
import { AutomaticMode } from "../actions"
import { DefaultMap } from "../utils"

const getChangesets = (state: State) => state.resource.changesets
const getReviewableFileChanges = (state: State) =>
  state.resource.reviewablefilechanges

const getReviewableFileChangesAsArray = createSelector(
  getReviewableFileChanges,
  (reviewableFileChanges) => castImmutable([...reviewableFileChanges.values()]),
)

export const getReviewableFileChangesForReview = createSelector(
  getReview,
  getReviewableFileChangesAsArray,
  (review, reviewableFileChanges) =>
    review
      ? reviewableFileChanges.filter((rfc) => rfc.review === review.id)
      : null,
)

export const getReviewableFileChangesPerReviewAndCommit = createSelector(
  getChangesets,
  getReviewableFileChanges,
  (changesets, reviewableFileChanges) => {
    const result = new DefaultMap<
      ReviewID,
      DefaultMap<CommitID, Set<ReviewableFileChange>>
    >(() => new DefaultMap(() => new Set()))
    for (const rfc of reviewableFileChanges.values()) {
      const changeset = changesets.byID.get(rfc.changeset)
      if (!changeset) {
        console.error({ rfc, changesets: changesets.byID })
        continue
      }
      const commitID = changeset.toCommit
      result.get(rfc.review).get(commitID).add(rfc)
    }
    return castImmutable(result)
  },
)

export const getReviewableFileChangesPerChangeset = createSelector(
  getReviewableFileChangesForReview,
  (reviewableFileChanges) => {
    const result = new DefaultMap<ChangesetID, Set<ReviewableFileChange>>(
      () => new Set(),
    )
    if (reviewableFileChanges)
      for (const rfc of reviewableFileChanges)
        result.get(rfc.changeset).add(rfc)
    return castImmutable(result.map)
  },
)

type GetAutomaticModeProps = { automaticMode?: AutomaticMode }

const getAutomaticMode = (state: State, props: GetAutomaticModeProps) =>
  props.automaticMode

export const getReviewableFileChangesForChangeset = createSelector(
  getChangesets,
  getReviewableFileChangesForReview,
  getChangeset,
  getAutomaticMode,
  (changesets, reviewableFileChanges, changeset, automaticMode) => {
    if (
      !reviewableFileChanges ||
      !changeset ||
      !changeset.contributingCommits ||
      !changeset.files
    ) {
      return null
    }
    const result = new DefaultMap<FileID, Set<ReviewableFileChange>>(
      () => new Set(),
    )
    for (const fileID of changeset.files) result.set(fileID, new Set())
    let found = false
    if (automaticMode === "everything") {
      for (const rfc of reviewableFileChanges) result.get(rfc.file).add(rfc)
      found = true
    } else if (changeset.contributingCommits.length === 1) {
      for (const rfc of reviewableFileChanges) {
        if (rfc.changeset === changeset.id) {
          result.get(rfc.file).add(rfc)
          found = true
        }
      }
    } else {
      const contributingChangesetIDs = new Set(
        changeset.contributingCommits.map((commitID) =>
          changesets.byCommits.get(String(commitID)),
        ),
      )
      for (const rfc of reviewableFileChanges) {
        if (contributingChangesetIDs.has(rfc.changeset)) {
          result.get(rfc.file).add(rfc)
          found = true
        }
      }
    }
    if (!found) return null
    return castImmutable(result.map)
  },
)
