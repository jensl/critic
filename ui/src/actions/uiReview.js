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

import { List } from "immutable"

import {
  setFlag,
  clearFlag,
  setValue,
  deleteValue,
  fileTreeViewReset,
  showAssignChangesDialog,
} from "./ui"

import { splitPath } from "../utils/Strings"

export const SET_REVIEW_ISSUES_MODE = "SET_REVIEW_ISSUES_MODE"
export const setReviewIssuesMode = (mode) => ({
  type: SET_REVIEW_ISSUES_MODE,
  mode,
})

export const IS_EDITING_SUMMARY_FLAG = "editing-review-summary"
export const IS_EDITING_BRANCH_FLAG = "editing-review-branch"
export const IS_VALID_BRANCH_NAME_FLAG = "is-valid-branch-name"
export const UNASSIGNED_CHANGES_DIALOG_VISIBLE_FLAG =
  "unassigned-changes-dialog-visible-flag"
export const SHOW_BRANCH_COMMITS_FLAG = "show-branch-commits"

export const EDIT_BRANCH_ERROR = "edit-review-branch-error"

export const editSummary = () => setFlag(IS_EDITING_SUMMARY_FLAG)
export const cancelEditSummary = () => clearFlag(IS_EDITING_SUMMARY_FLAG)

export const editBranch = () => setFlag(IS_EDITING_BRANCH_FLAG)
export const cancelEditBranch = () => clearFlag(IS_EDITING_BRANCH_FLAG)
export const setIsValidBranchName = (value) =>
  (value ? setFlag : clearFlag)(IS_VALID_BRANCH_NAME_FLAG)

export const showUnassignedChangesDialog = (reviewID) => (dispatch) => {
  dispatch(fileTreeViewReset())
  dispatch(showAssignChangesDialog({ reviewID, mode: "unassigned-files" }))
}

export const setEditBranchError = (error) => setValue(EDIT_BRANCH_ERROR, error)
export const clearEditBranchError = () => deleteValue(EDIT_BRANCH_ERROR)

export const showAssignChangesToSelfDialog = (reviewID) => (
  dispatch,
  getState
) => {
  const state = getState()
  const { user } = state.ui.rest
  const { reviewfilters, files } = state.resource
  const expandedFolders = new Set()
  const selectedFolders = new Set()
  const selectedFileIDs = new Set()
  for (const rf of reviewfilters.values()) {
    if (rf.review !== reviewID) continue
    if (rf.subject !== user.id) continue
    if (rf.type !== "reviewer") continue
    if (rf.path.endsWith("/")) selectedFolders.add(rf.path)
    else selectedFileIDs.add(files.byPath.get(rf.path))
    let dirname = rf.path
    while (true) {
      dirname = splitPath(dirname)[0]
      if (dirname === null) break
      expandedFolders.add(dirname)
    }
  }
  dispatch(
    fileTreeViewReset({
      expandedFolders,
      selectedFolders,
      selectedFileIDs,
      lockedFolders: selectedFolders,
      lockedFileIDs: selectedFileIDs,
    })
  )
  dispatch(showAssignChangesDialog({ reviewID, mode: "assign-self" }))
}

export const showBranchCommits = () => setFlag(SHOW_BRANCH_COMMITS_FLAG)
export const showReviewableCommits = () => clearFlag(SHOW_BRANCH_COMMITS_FLAG)

export const DISPLAY_CREATE_REVIEW_DIALOG = "DISPLAY_CREATE_REVIEW_DIALOG"
export const displayCreateReviewDialog = ({
  branch = null,
  commitIDs = null,
  repository = null,
  fromSelection = false,
}) => (dispatch, getState) => {
  const state = getState()
  if (fromSelection) commitIDs = new List(state.ui.selectionScope.selectedIDs)
  dispatch({
    type: DISPLAY_CREATE_REVIEW_DIALOG,
    branch,
    repository,
    commitIDs,
  })
}

export const DISMISS_CREATE_REVIEW_DIALOG = "DISMISS_CREATE_REVIEW_DIALOG"
export const dismissCreateReviewDialog = () => ({
  type: DISMISS_CREATE_REVIEW_DIALOG,
})
