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

import { immerable } from "immer"

import { primaryMap } from "../reducers/resource"
import {
  ChangesetID,
  FileID,
  ReviewableFileChangeID,
  ReviewID,
  UserID,
} from "./types"

type ReviewableFileChangeData = {
  id: number
  review: number
  changeset: number
  file: number
  deleted_lines: number
  inserted_lines: number
  is_reviewed: boolean
  reviewed_by: number[]
  assigned_reviewers: number[]
  draft_changes: DraftChangesData
}

type ReviewableFileChangeProps = {
  id: number
  review: number
  changeset: number
  file: number
  deleted_lines: number
  inserted_lines: number
  is_reviewed: boolean
  reviewed_by: ReadonlySet<number>
  assigned_reviewers: ReadonlySet<number>
  draft_changes: DraftChanges | null
}

class ReviewableFileChange {
  [immerable] = true

  constructor(
    readonly id: ReviewableFileChangeID,
    readonly review: ReviewID,
    readonly changeset: ChangesetID,
    readonly file: FileID,
    readonly deletedLines: number,
    readonly insertedLines: number,
    readonly isReviewed: boolean,
    readonly reviewedBy: ReadonlySet<UserID>,
    readonly assignedReviewers: ReadonlySet<UserID>,
    readonly draftChanges: DraftChanges | null,
  ) {}

  static new(props: ReviewableFileChangeProps) {
    return new ReviewableFileChange(
      props.id,
      props.review,
      props.changeset,
      props.file,
      props.deleted_lines,
      props.inserted_lines,
      props.is_reviewed,
      props.reviewed_by,
      props.assigned_reviewers,
      props.draft_changes,
    )
  }

  static prepare(value: ReviewableFileChangeData): ReviewableFileChangeProps {
    return {
      ...value,
      assigned_reviewers: new Set<number>(value.assigned_reviewers || []),
      reviewed_by: new Set<number>(value.reviewed_by || []),
      draft_changes:
        value.draft_changes && DraftChanges.new(value.draft_changes),
    }
  }

  static reducer = primaryMap<ReviewableFileChange, number>(
    "reviewablefilechanges",
  )

  get props(): ReviewableFileChangeProps {
    return {
      ...this,
      deleted_lines: this.deletedLines,
      inserted_lines: this.insertedLines,
      is_reviewed: this.isReviewed,
      reviewed_by: this.reviewedBy,
      assigned_reviewers: this.assignedReviewers,
      draft_changes: this.draftChanges,
    }
  }

  isReviewedBy(userID: UserID) {
    return this.draftChanges?.author === userID
      ? this.draftChanges.newIsReviewed
      : this.reviewedBy.has(userID)
  }
}

type DraftChangesData = {
  author: number
  new_is_reviewed: boolean
}

type DraftChangesProps = DraftChangesData

class DraftChanges {
  [immerable] = true

  constructor(readonly author: UserID, readonly newIsReviewed: boolean) {}

  static new(props: DraftChangesProps) {
    return new DraftChanges(props.author, props.new_is_reviewed)
  }
}

export default ReviewableFileChange
