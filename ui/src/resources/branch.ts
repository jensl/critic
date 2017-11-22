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

import produce from "immer"
import { combineReducers } from "redux"
import { primaryMap, lookupMap } from "../reducers/resource"
import { Action, SET_CREATED_BRANCHES, SET_UPDATED_BRANCHES } from "../actions"
import { BranchID, CommitID, RepositoryID } from "./types"

const branchList = (
  actionType: typeof SET_CREATED_BRANCHES | typeof SET_UPDATED_BRANCHES
) =>
  produce(
    (state: BranchID[], action: Action) =>
      action.type === actionType ? action.branchIDs : state,
    []
  )

const created = branchList(SET_CREATED_BRANCHES)
const updated = branchList(SET_UPDATED_BRANCHES)

type BranchProps = {
  id: number
  name: string
  repository: number
  base_branch: null | number
  head: number
  size: number
}

export class Branch {
  constructor(
    readonly id: BranchID,
    readonly name: string,
    readonly repository: RepositoryID,
    readonly baseBranch: null | number,
    readonly head: CommitID,
    readonly size: number
  ) {}

  static new(props: BranchProps) {
    return new Branch(
      props.id,
      props.name,
      props.repository,
      props.base_branch,
      props.head,
      props.size
    )
  }

  static reducer = combineReducers({
    byID: primaryMap<Branch, number>("branches"),
    byName: lookupMap<Branch, string, number>(
      "branches",
      (branch) => `${branch.repository}:${branch.name}`
    ),
    created,
    updated,
  })

  get props(): BranchProps {
    return { ...this, base_branch: this.baseBranch }
  }
}

export default Branch

export type Branches = ReturnType<typeof Branch.reducer>
