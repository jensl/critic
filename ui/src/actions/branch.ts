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

import { fetch, include, withArgument, withParameters } from "../resources"
import { AsyncThunk, Dispatch, Thunk } from "../state"
import {
  BRANCH_COMMITS_UPDATE,
  SET_CREATED_BRANCHES,
  SET_UPDATED_BRANCHES,
  SET_RECENT_BRANCHES,
  Action,
} from "."
import { BranchID, CommitID, UserID, RepositoryID } from "../resources/types"
import { RequestParams } from "../utils/Fetch.types"

export const setCreatedBranches = (branchIDs: BranchID[]): Action => ({
  type: SET_CREATED_BRANCHES,
  branchIDs,
})

export const setUpdatedBranches = (branchIDs: BranchID[]): Action => ({
  type: SET_UPDATED_BRANCHES,
  branchIDs,
})

type BranchCommitsUpdateKey = {
  branchID: number
  afterRebaseID?: number | null
  offset?: number | null
  count?: number | null
}
export const branchCommitsUpdate = (
  {
    branchID,
    afterRebaseID = null,
    offset = null,
    count = null,
  }: BranchCommitsUpdateKey,
  commitIDs: CommitID[],
): Action => ({
  type: BRANCH_COMMITS_UPDATE,
  branchID,
  afterRebaseID,
  offset,
  count,
  commitIDs,
})

export const setRecentBranches = (
  repositoryID: number,
  offset: number,
  count: number,
  branchIDs: BranchID[],
): Action => ({
  type: SET_RECENT_BRANCHES,
  repositoryID,
  offset,
  count,
  branchIDs,
})

export const loadCreated = (
  userID: number,
  count = 5,
): AsyncThunk<void> => async (dispatch) => {
  const { primary } = await dispatch(
    fetch(
      "branches",
      withParameters({
        created_by: userID,
        exclude_reviewed_branches: "yes",
        count,
      }),
      include("repositories"),
    ),
  )
  if (primary) dispatch(setCreatedBranches(primary.map((branch) => branch.id)))
}

const loadUpdated = (userID: number, count = 5): AsyncThunk<void> => async (
  dispatch,
) => {
  const { primary } = await dispatch(
    fetch(
      "branches",
      withParameters({
        updated_by: userID,
        exclude_reviewed_branches: "yes",
        count,
      }),
    ),
  )
  if (primary) dispatch(setUpdatedBranches(primary.map((branch) => branch.id)))
}

export const loadBranchesForDashboard = (userID: UserID): Thunk<void> => (
  dispatch,
) => {
  dispatch(loadCreated(userID))
  dispatch(loadUpdated(userID))
}

type BranchByIDParam = { branchID: BranchID }
type BranchByNameParams = { repositoryID: RepositoryID; name: string }

const isBranchByIDParam = (
  input: BranchByIDParam | BranchByNameParams,
): input is BranchByIDParam => "branchID" in input

export const loadBranch = (input: BranchByIDParam | BranchByNameParams) =>
  fetch(
    "branches",
    isBranchByIDParam(input)
      ? withArgument(input.branchID)
      : withParameters({ repository: input.repositoryID, name: input.name }),
  )

type BranchCommitsOptions = {
  afterRebaseID?: number | null
  offset?: number
  count?: number
}

export const loadBranchCommits = (
  branchID: BranchID,
  { afterRebaseID = null, offset = 0, count = 25 }: BranchCommitsOptions = {},
) => async (dispatch: Dispatch) => {
  const params: RequestParams = { offset, count, branch: branchID }
  if (afterRebaseID !== null) params.after_rebase = afterRebaseID
  const { primary } = await dispatch(fetch("commits", withParameters(params)))
  if (primary) {
    const key: BranchCommitsUpdateKey =
      afterRebaseID !== null ? { branchID, afterRebaseID } : { branchID }
    Object.assign(key, { offset, count })
    dispatch(
      branchCommitsUpdate(
        key,
        primary.map((commit) => commit.id),
      ),
    )
  }
}

export const loadRecentBranches = (
  repositoryID: RepositoryID,
  {
    offset = 0,
    count = 10,
  }: {
    offset?: number
    count?: number
  },
) => async (dispatch: Dispatch) => {
  const { primary } = await dispatch(
    fetch("branches", {
      params: { repository: repositoryID, order_by: "updated", offset, count },
      include: ["commits", "branches"],
    }),
  )
  if (primary) {
    const branchIDs = primary.map((branch) => branch.id)
    dispatch(setRecentBranches(repositoryID, offset, count, branchIDs))
  }
}
