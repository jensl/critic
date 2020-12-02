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
import { CommentID, CommitID, FileID, RebaseID, ReviewTagID } from "./types"

type ReviewData = {
  id: number
  state: "draft" | "open" | "closed" | "dropped"
  is_accepted: boolean
  summary: string
  description: string
  repository: number
  branch: number
  owners: number[]
  active_reviewers: number[]
  assigned_reviewers: number[]
  watchers: number[]
  partitions: PartitionData[]
  issues: CommentID[]
  notes: CommentID[]
  pending_update: number | null
  pending_rebase: number | null
  progress: Progress
  progress_per_commit: CommitChangeCountData[]
  tags: number[]
  last_changed: number
  integration: IntegrationData | null

  is_partial?: boolean
}

type ReviewProps = {
  id: number
  state: "draft" | "open" | "closed" | "dropped"
  is_accepted: boolean
  summary: string
  description: string
  repository: number
  branch: number
  owners: ReadonlySet<number>
  active_reviewers: ReadonlySet<number>
  assigned_reviewers: ReadonlySet<number>
  watchers: ReadonlySet<number>
  partitions: readonly Partition[]
  issues: readonly CommentID[]
  notes: readonly CommentID[]
  pending_update: number | null
  pending_rebase: number | null
  progress: Progress
  progress_per_commit: ReadonlyMap<CommitID, CommitChangeCount>
  tags: ReadonlySet<ReviewTagID>
  last_changed: number
  integration: Integration | null

  is_partial?: boolean
}

class Review {
  [immerable] = true

  constructor(
    readonly id: number,
    readonly state: "draft" | "open" | "closed" | "dropped",
    readonly isAccepted: boolean,
    readonly summary: string,
    readonly description: string,
    readonly repository: number,
    readonly branch: number,
    readonly owners: ReadonlySet<number>,
    readonly activeReviewers: ReadonlySet<number>,
    readonly assignedReviewers: ReadonlySet<number>,
    readonly watchers: ReadonlySet<number>,
    readonly partitions: readonly Partition[],
    readonly issues: readonly CommentID[],
    readonly notes: readonly CommentID[],
    readonly pendingUpdate: number | null,
    readonly pendingRebase: number | null,
    readonly progress: Progress,
    readonly progressPerCommit: ReadonlyMap<CommitID, CommitChangeCount>,
    readonly tags: ReadonlySet<ReviewTagID>,
    readonly lastChanged: number,
    readonly integration: Integration | null,
    readonly isPartial: boolean = false,
  ) {}

  static new(props: ReviewProps) {
    return new Review(
      props.id,
      props.state,
      props.is_accepted,
      props.summary,
      props.description,
      props.repository,
      props.branch,
      props.owners,
      props.active_reviewers,
      props.assigned_reviewers,
      props.watchers,
      props.partitions,
      props.issues,
      props.notes,
      props.pending_update,
      props.pending_rebase,
      props.progress,
      props.progress_per_commit,
      props.tags,
      props.last_changed,
      props.integration,
      props.is_partial,
    )
  }

  static prepare(value: ReviewData): ReviewProps {
    return {
      ...value,
      owners: new Set<number>(value.owners || []),
      active_reviewers: new Set<number>(value.active_reviewers || []),
      assigned_reviewers: new Set<number>(value.assigned_reviewers || []),
      watchers: new Set<number>(value.watchers || []),
      partitions: value.partitions?.map(Partition.new) || [],
      progress_per_commit: new Map(
        (value.progress_per_commit || []).map((data) => [
          data.commit,
          CommitChangeCount.new(data),
        ]),
      ),
      tags: new Set<number>(value.tags || []),
      integration: value.integration && Integration.make(value.integration),
    }
  }

  static reducer = primaryMap<Review, number>("reviews")

  get props(): ReviewProps {
    return {
      ...this,
      is_accepted: this.isAccepted,
      active_reviewers: this.activeReviewers,
      assigned_reviewers: this.assignedReviewers,
      pending_update: this.pendingUpdate,
      pending_rebase: this.pendingRebase,
      progress_per_commit: this.progressPerCommit,
      last_changed: this.lastChanged,
      is_partial: this.isPartial,
    }
  }
}

type PartitionData = {
  commits: readonly CommitID[]
  rebase: RebaseID | null
}

type PartitionProps = PartitionData

export class Partition {
  [immerable] = true

  constructor(
    readonly commits: readonly CommitID[],
    readonly rebase: RebaseID | null,
  ) {}

  static new(props: PartitionProps) {
    return new Partition(props.commits, props.rebase)
  }
}

type CommitChangeCountData = {
  commit: number
  total_changes: number
  reviewed_changes: number
}

type CommitChangeCountProps = CommitChangeCountData

class CommitChangeCount {
  [immerable] = true

  constructor(
    readonly commit: number,
    readonly totalChanges: number,
    readonly reviewedChanges: number,
  ) {}

  static new(props: CommitChangeCountProps) {
    return new CommitChangeCount(
      props.commit,
      props.total_changes,
      props.reviewed_changes,
    )
  }
}

type ProgressData = {
  reviewing: number
  issues: number
}

type ProgressProps = ProgressData

class Progress {
  [immerable] = true

  constructor(readonly reviewing: number, readonly issues: number) {}

  static new(props: ProgressProps) {
    return new Progress(props.reviewing, props.issues)
  }
}

type IntegrationData = {
  target_branch: number
  commits_behind: number
  state: string
  squashed: boolean
  autosquashed: boolean
  strategy_used: string | null
  conflicts: FileID[]
  error_message: string | null
}

type IntegrationProps = {
  target_branch: number
  commits_behind: number
  state: string
  squashed: boolean
  autosquashed: boolean
  strategy_used: string | null
  conflicts: ReadonlySet<FileID>
  error_message: string | null
}

class Integration {
  [immerable] = true

  constructor(
    readonly targetBranch: number,
    readonly commitsBehind: number,
    readonly state: string,
    readonly squashed: boolean,
    readonly autosquashed: boolean,
    readonly strategyUsed: string | null,
    readonly conflicts: ReadonlySet<FileID>,
    readonly errorMessage: string | null,
  ) {}

  static new(props: IntegrationProps) {
    return new Integration(
      props.target_branch,
      props.commits_behind,
      props.state,
      props.squashed,
      props.autosquashed,
      props.strategy_used,
      props.conflicts,
      props.error_message,
    )
  }

  static make(value: IntegrationData) {
    return Integration.new({ ...value, conflicts: new Set(value.conflicts) })
  }
}

export default Review

export type Reviews = ReturnType<typeof Review.reducer>
