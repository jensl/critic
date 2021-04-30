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

import {
  fetch,
  include,
  withArgument,
  withContext,
  withParameters,
} from "../resources"
import { AsyncThunk, Dispatch, Thunk } from "../state"
import {
  BRANCH_COMMITS_UPDATE,
  SET_CREATED_BRANCHES,
  SET_UPDATED_BRANCHES,
  SET_RECENT_BRANCHES,
  Action,
} from "."
import {
  BranchID,
  CommitID,
  UserID,
  RepositoryID,
  RebaseID,
} from "../resources/types"
import { RequestParams } from "../utils/Fetch.types"
import Branch from "../resources/branch"
import { PaginationInfo } from "../resources/fetch"
import { assertNotNull } from "../debug"
import { PaginationThunk } from "../utils/Pagination"
import Commit from "../resources/commit"

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

type BranchByNameParams = { repositoryID: RepositoryID; name: string }

export const loadBranch = (branchID: BranchID) =>
  fetch("branches", withArgument(branchID))

export const loadBranchByName = (repository: RepositoryID, name: string) =>
  fetch("branches", withParameters({ repository, name }))

type BranchCommitsOptions = {
  afterRebaseID?: number | null
  offset?: number
  count?: number
}

export const loadBranchCommits = (
  branchID: BranchID,
  offset: number,
  count: number,
): PaginationThunk<Commit> => async (dispatch) => {
  const { primary, pagination } = await dispatch(
    fetch(
      "commits",
      withContext("branches", branchID),
      withParameters({ offset, count }),
    ),
  )
  assertNotNull(pagination)
  return [primary, pagination]
}

export const loadBranchCommitsAfterRebase = (
  branchID: BranchID,
  afterRebaseID: RebaseID,
): AsyncThunk<Commit[]> => async (dispatch) => {
  const { primary } = await dispatch(
    fetch(
      "commits",
      withContext("branches", branchID),
      withParameters({ after_rebase: afterRebaseID }),
    ),
  )
  if (primary) {
    dispatch(
      branchCommitsUpdate(
        { branchID, afterRebaseID },
        primary.map((commit) => commit.id),
      ),
    )
  }
  return primary
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

export const loadRepositoryBranches = (
  repositoryID: RepositoryID,
  offset: number,
  count: number,
): AsyncThunk<[Branch[], PaginationInfo]> => async (dispatch) => {
  const { primary, pagination } = await dispatch(
    fetch(
      "branches",
      withContext("repositories", repositoryID),
      withParameters({ offset, count }),
    ),
  )
  assertNotNull(pagination)
  return [primary, pagination]
}
