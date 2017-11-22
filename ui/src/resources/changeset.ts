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

import { RequestParams, FetchJSONParams } from "../utils/Fetch.types"
import { assertString, assertNumber } from "../debug"
import { ResourceData } from "../types"
import { Action, AutomaticMode } from "../actions"
import { combineReducers } from "redux"
import { lookupManyMap, primaryMap } from "../reducers/resource"
import {
  ChangesetID,
  RepositoryID,
  ReviewID,
  FileID,
  CommitID,
  ReviewableFileChangeID,
  CommentID,
} from "./types"
import { SET_AUTOMATIC_CHANGESET } from "../actions"
import produce from "../reducers/immer"

export type CompletionLevel =
  | "structure"
  | "changedlines"
  | "analysis"
  | "syntaxhighlight"
  | "full"

type ChangesetData = {
  id: ChangesetID
  completion_level: CompletionLevel[]
  from_commit: CommitID
  to_commit: CommitID
  is_direct: boolean
  files: FileID[]
  contributing_commits: CommitID[]
  review_state: ReviewState | null
}

type ChangesetProps = {
  id: ChangesetID
  completion_level: ReadonlySet<CompletionLevel>
  from_commit: CommitID
  to_commit: CommitID
  is_direct: boolean
  files: readonly FileID[]
  contributing_commits: readonly CommitID[]
  review_state: ReviewState | null
}

type RequestArguments = {
  byID?: ChangesetID
  byCommits?: ByCommits
  automatic?: AutomaticMode
}

type RequestOptions = {
  reviewID?: ReviewID
  repositoryID?: RepositoryID
  onlyIfComplete?: false | string
}

const automatic = produce<Map<string, ChangesetID>>(
  (draft: Map<string, ChangesetID>, action: Action) => {
    if (action.type === SET_AUTOMATIC_CHANGESET)
      draft.set(`${action.reviewID}:${action.automatic}`, action.changesetID)
  },
  new Map()
)

class Changeset {
  constructor(
    readonly id: ChangesetID,
    readonly completionLevel: ReadonlySet<CompletionLevel>,
    readonly fromCommit: CommitID,
    readonly toCommit: CommitID,
    readonly isDirect: boolean,
    readonly files: readonly FileID[],
    readonly contributingCommits: readonly CommitID[],
    readonly reviewState: ReviewState | null
  ) {}

  static new(props: ChangesetProps) {
    return new Changeset(
      props.id,
      props.completion_level,
      props.from_commit,
      props.to_commit,
      props.is_direct,
      props.files,
      props.contributing_commits,
      props.review_state
    )
  }

  static prepare(value: ChangesetData): ChangesetProps {
    return {
      ...value,
      completion_level: new Set(value.completion_level || []),
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
      }
    ),
    automatic,
  })

  static createRequest(
    { byID, byCommits, automatic }: RequestArguments,
    { reviewID, repositoryID, onlyIfComplete = false }: RequestOptions
  ): FetchJSONParams {
    var path = "changesets"
    const params: RequestParams = {}

    if (onlyIfComplete) {
      params.only_if_complete = onlyIfComplete
    }

    if (typeof byID === "number") {
      path += "/" + byID
    } else if (byCommits) {
      const { fromCommit, toCommit, singleCommit } = byCommits

      if (singleCommit) params.commit = singleCommit
      else {
        if (fromCommit) params.from = fromCommit
        assertString(toCommit)
        params.to = toCommit as string
      }
    } else {
      assertString(automatic)
      params.automatic = automatic as string
    }

    const include = ["commits", "filechanges", "files"]

    if (typeof reviewID === "number") {
      params.review = String(reviewID)
      include.push(
        "changesets",
        "comments",
        "replies",
        "reviewablefilechanges",
        "users"
      )
      // Exclude original comment locations, since they're likely to reference
      // other changesets that we don't care about in this context. The translated
      // location will still be included.
      params["fields[comments]"] = "-location"
    } else {
      assertNumber(repositoryID)
      params.repository = String(repositoryID)
    }

    console.error({
      path,
      params,
      include,
      expectStatus: [200, 202],
    })

    return {
      path,
      params,
      include,
      expectStatus: [200, 202],
    }
  }

  get props(): ChangesetProps {
    return {
      ...this,
      completion_level: this.completionLevel,
      from_commit: this.fromCommit,
      to_commit: this.toCommit,
      is_direct: this.isDirect,
      contributing_commits: this.contributingCommits,
      review_state: this.reviewState,
    }
  }
}

type ReviewStateData = {
  review: ReviewID
  comments: readonly CommentID[]
  reviewablefilechanges: readonly ReviewableFileChangeID[]
}

type ReviewStateProps = ReviewStateData

export class ReviewState {
  constructor(
    readonly review: ReviewID,
    readonly comments: readonly CommentID[],
    readonly reviewableFileChanges: readonly ReviewableFileChangeID[]
  ) {}

  static new(props: ReviewStateProps) {
    return new ReviewState(
      props.review,
      props.comments,
      props.reviewablefilechanges
    )
  }

  static make(value: ResourceData | null) {
    return value && ReviewState.new(value as ReviewStateProps)
  }
}

type ByCommits = {
  fromCommit?: string
  toCommit?: string
  singleCommit?: string
}

export default Changeset

export type Changesets = ReturnType<typeof Changeset.reducer>
