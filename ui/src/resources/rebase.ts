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
import { RebaseID, ReviewID, UserID, CommitID } from "./types"

type RebaseData = {
  id: RebaseID
  review: ReviewID
  creator: UserID
  type: "history-rewrite" | "move"
  branchupdate: number | null
  old_upstream: CommitID | null
  new_upstream: CommitID | null
  equivalent_merge: CommitID | null
  replayed_rebase: CommitID | null
}

type RebaseProps = RebaseData

class Rebase {
  [immerable] = true

  constructor(
    readonly id: RebaseID,
    readonly review: ReviewID,
    readonly creator: UserID,
    readonly type: "history-rewrite" | "move",
    readonly branchupdate: number | null,
    readonly oldUpstream: CommitID | null,
    readonly newUpstream: CommitID | null,
    readonly equivalentMerge: CommitID | null,
    readonly replayedRebase: CommitID | null,
  ) {}
  static new(props: RebaseProps) {
    return new Rebase(
      props.id,
      props.review,
      props.creator,
      props.type,
      props.branchupdate,
      props.old_upstream,
      props.new_upstream,
      props.equivalent_merge,
      props.replayed_rebase,
    )
  }

  static reducer = primaryMap<Rebase, number>("rebases")

  get props(): RebaseProps {
    return {
      ...this,
      old_upstream: this.oldUpstream,
      new_upstream: this.newUpstream,
      equivalent_merge: this.equivalentMerge,
      replayed_rebase: this.replayedRebase,
    }
  }
}

export default Rebase

export type Rebases = ReturnType<typeof Rebase.reducer>
