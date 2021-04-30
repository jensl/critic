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

import { combineReducers } from "redux"
import { immerable } from "immer"

import { assertNumber } from "../debug"
import { ResourceData } from "../types"
import {
  Action,
  AutomaticChangesetEmpty,
  AutomaticChangesetImpossible,
  AutomaticMode,
} from "../actions"
import { lookupManyMap, primaryMap } from "../reducers/resource"
import {
  ChangesetID,
  RepositoryID,
  ReviewID,
  FileID,
  CommitID,
  ReviewableFileChangeID,
  CommentID,
  RequestOptions,
} from "./types"
import { SET_AUTOMATIC_CHANGESET } from "../actions"
import produce from "../reducers/immer"
import {
  expectStatuses,
  include,
  withArgument,
  withParameters,
} from "./requestoptions"

export type CompletionLevel =
  | "structure"
  | "changedlines"
  | "analysis"
  | "syntaxhighlight"
  | "full"

type ChangesetData = {
  id: ChangesetID
  completion_level: CompletionLevel[]
  progress: ProgressData | null
  repository: RepositoryID
  from_commit: CommitID | null
  to_commit: CommitID
  is_direct: boolean
  files: FileID[]
  contributing_commits: CommitID[] | null
  review_state: ReviewState | null
}

type ChangesetProps = {
  id: ChangesetID
  completion_level: ReadonlySet<CompletionLevel>
  progress: Progress | null
  repository: RepositoryID
  from_commit: CommitID | null
  to_commit: CommitID
  is_direct: boolean
  files: readonly FileID[] | null
  contributing_commits: readonly CommitID[] | null
  review_state: ReviewState | null
}

type ByID = { byID: ChangesetID }
type BySingleCommit = {
  singleCommit: string
}
type ByCommitRange = {
  fromCommit?: string
  toCommit: string
}
type ByCommits = BySingleCommit | ByCommitRange
type Automatic = { automatic: AutomaticMode }

type RequestArguments = ByID | ByCommits | Automatic

type ChangesetRequestOptions = {
  reviewID?: ReviewID
  repositoryID?: RepositoryID
  onlyIfComplete?: false | string
}

type AutomaticMap = Map<
  string,
  ChangesetID | AutomaticChangesetEmpty | AutomaticChangesetImpossible
>

const automatic = produce<AutomaticMap>(
  (draft: AutomaticMap, action: Action) => {
    if (action.type === SET_AUTOMATIC_CHANGESET)
      draft.set(`${action.reviewID}:${action.automatic}`, action.changesetID)
  },
  new Map(),
)

class Changeset {
  [immerable] = true

  constructor(
    readonly id: ChangesetID,
    readonly completionLevel: ReadonlySet<CompletionLevel>,
    readonly progress: Progress | null,
    readonly repository: RepositoryID,
    readonly fromCommit: CommitID | null,
    readonly toCommit: CommitID,
    readonly isDirect: boolean,
    readonly files: readonly FileID[] | null,
    readonly contributingCommits: readonly CommitID[] | null,
    readonly reviewState: ReviewState | null,
  ) {}

  static new(props: ChangesetProps) {
    return new Changeset(
      props.id,
      props.completion_level,
      props.progress,
      props.repository,
      props.from_commit,
      props.to_commit,
      props.is_direct,
      props.files,
      props.contributing_commits,
      props.review_state,
    )
  }

  static prepare(value: ChangesetData): ChangesetProps {
    return {
      ...value,
      completion_level: new Set(value.completion_level || []),
      progress: Progress.make(value.progress),
      review_state: ReviewState.make(value.review_state),
    }
  }

  static reducer = combineReducers({
    byID: primaryMap<Changeset, ChangesetID>("changesets"),
    byCommits: lookupManyMap<Changeset, string, ChangesetID>(
      "changesets",
      (changeset) => {
        const { isDirect, fromCommit, toCommit } = changeset
        const keys: string[] = []
        if (isDirect) keys.push(String(toCommit))
        if (fromCommit !== null) keys.push(`${fromCommit}..${toCommit}`)
        else keys.push(`..${toCommit}`)
        return keys
      },
    ),
    automatic,
  })

  static requestOptions(
    argument: RequestArguments,
    { reviewID, repositoryID, onlyIfComplete = false }: ChangesetRequestOptions,
  ): RequestOptions[] {
    const options = []

    if (onlyIfComplete) {
      options.push(withParameters({ only_if_complete: onlyIfComplete }))
    }

    if ("byID" in argument) {
      options.push(withArgument(argument.byID))
    } else if ("singleCommit" in argument)
      options.push(withParameters({ commit: argument.singleCommit }))
    else if ("toCommit" in argument) {
      const { fromCommit, toCommit } = argument
      if (fromCommit)
        options.push(withParameters({ from: fromCommit, to: toCommit }))
      else options.push(withParameters({ to: toCommit }))
    } else {
      const { automatic } = argument
      options.push(withParameters({ automatic }))
    }

    options.push(include("commits", "filechanges", "files"))

    if (typeof reviewID === "number") {
      options.push(
        withParameters({
          review: reviewID,
          // Exclude original comment locations, since they're likely to
          // reference other changesets that we don't care about in this
          // context. The translated location will still be included.
          ["fields[comments]"]: "-location",
        }),
      )
      options.push(
        include(
          "changesets",
          "comments",
          "replies",
          "reviewablefilechanges",
          "users",
        ),
      )
    } else if (!("byID" in argument)) {
      assertNumber(
        repositoryID,
        "Changeset.requestOptions() expected a repositoryID",
      )
      options.push(withParameters({ repository: repositoryID }))
    }

    options.push(expectStatuses(200, 202))
    return options
  }

  get props(): ChangesetProps {
    return {
      ...this,
      completion_level: this.completionLevel,
      progress: this.progress,
      from_commit: this.fromCommit,
      to_commit: this.toCommit,
      is_direct: this.isDirect,
      contributing_commits: this.contributingCommits,
      review_state: this.reviewState,
    }
  }
}

type ProgressData = {
  analysis: number
  syntax_highlight: number
}

type ProgressProps = ProgressData

export class Progress {
  [immerable] = true

  constructor(readonly analysis: number, readonly syntaxHighlight: number) {}

  static new(props: ProgressProps) {
    return new Progress(props.analysis, props.syntax_highlight)
  }

  static make(value: ProgressData | null) {
    return value && Progress.new(value as ProgressProps)
  }
}

type ReviewStateData = {
  review: ReviewID
  comments: readonly CommentID[]
  reviewablefilechanges: readonly ReviewableFileChangeID[]
}

type ReviewStateProps = ReviewStateData

export class ReviewState {
  [immerable] = true

  constructor(
    readonly review: ReviewID,
    readonly comments: readonly CommentID[],
    readonly reviewableFileChanges: readonly ReviewableFileChangeID[],
  ) {}

  static new(props: ReviewStateProps) {
    return new ReviewState(
      props.review,
      props.comments,
      props.reviewablefilechanges,
    )
  }

  static make(value: ResourceData | null) {
    return value && ReviewState.new(value as ReviewStateProps)
  }
}

export default Changeset

export type Changesets = ReturnType<typeof Changeset.reducer>
