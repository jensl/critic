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

import { showToast } from "./uiToast"

import { toggleReviewableFileChange } from "./reviewableFilechange.js"
import { parseChangesetPath, generateLinkPath } from "../utils/Changeset"

export const EXPAND_FILE = "EXPAND_FILE"
export const _expandFile = (fileID) => ({
  type: EXPAND_FILE,
  fileID,
})

export const EXPAND_MANY_FILES = "EXPAND_MANY_FILES"
export const _expandManyFiles = (fileIDs) => ({
  type: EXPAND_MANY_FILES,
  fileIDs,
})

export const COLLAPSE_FILE = "COLLAPSE_FILE"
export const _collapseFile = (fileID) => ({
  type: COLLAPSE_FILE,
  fileID,
})

export const COLLAPSE_MANY_FILES = "COLLAPSE_MANY_FILES"
export const collapseManyFiles = (fileIDs) => ({
  type: COLLAPSE_MANY_FILES,
  fileIDs,
})

export const SET_EXPANDED_FILES = "SET_EXPANDED_FILES"
export const setExpandedFiles = (fileIDs) => ({
  type: SET_EXPANDED_FILES,
  fileIDs,
})

export const SET_EXPANDABLE_FILES = "SET_EXPANDABLE_FILES"
export const setExpandableFiles = (fileIDs) => ({
  type: SET_EXPANDABLE_FILES,
  fileIDs,
})

export const SET_CURRENT_FILE = "SET_CURRENT_FILE"
export const setCurrentFile = (fileID) => ({
  type: SET_CURRENT_FILE,
  fileID,
})

const isInView = (inView, fileKey, part) =>
  inView.has(`file:${fileKey}:${part}`)

export const collapseFile = (
  location,
  match,
  history,
  expandedFileIDs,
  fileKey,
  reviewableFileChanges
) => (dispatch, getState) => {
  const { inView } = getState().ui
  const bottomWasInView = isInView(inView, fileKey, "bottom")

  if (reviewableFileChanges && bottomWasInView) {
    dispatch(toggleReviewableFileChange(true, { reviewableFileChanges }))
  }

  const linkPath = generateLinkPath({
    location,
    match,
    expandedFileIDs: expandedFileIDs.delete(fileKey),
  })
  history.replace(linkPath)
}

export const expandNextFile = ({
  changeset,
  review,
  location,
  match,
  history,
}) => (dispatch, getState) => {
  const state = getState()
  const { inView, rest } = state.ui
  const { expandableFileIDs, currentFileID } = rest
  var { changesetID, expandedFileIDs } = parseChangesetPath(location.pathname)

  const session = state.resource.sessions.get("current")
  const signedInUser = state.resource.users.byID.get(
    session && session.user,
    null
  )

  const update = (expandedFileIDs) => {
    const linkPath = generateLinkPath({
      location,
      match,
      expandedFileIDs,
    })
    history.replace(linkPath)
  }

  if (currentFileID === null) {
    return false
  } else if (!expandedFileIDs.has(currentFileID)) {
    update(expandedFileIDs.add(currentFileID))
    return true
  } else if (!isInView(inView, currentFileID, "bottom")) {
    return false
  }

  expandedFileIDs = expandedFileIDs.delete(currentFileID)

  if (review && signedInUser) {
    dispatch(
      toggleReviewableFileChange(true, {
        reviewID: review.id,
        changesetID: changeset.id,
        fileID: currentFileID,
      })
    ).then((didReview) => {
      let path
      for (let fileID of changeset.files) {
        if (fileID === currentFileID) {
          path = state.resource.files.byID.get(fileID).path
        }
      }
      if (didReview) {
        dispatch(
          showToast({
            title: "File marked as reviewed",
            content: path,
          })
        )
      }
    })
  }

  const currentIndex = expandableFileIDs.indexOf(currentFileID)
  if (currentIndex === expandableFileIDs.size - 1) {
    const nextFileID = expandableFileIDs.get(0)
    dispatch(setCurrentFile(nextFileID))
    update(expandedFileIDs)
    return false
  } else {
    const nextFileID = expandableFileIDs.get(currentIndex + 1)
    dispatch(setCurrentFile(nextFileID))
    update(expandedFileIDs.add(nextFileID))
    return true
  }
}

export const expandFiles = (location, match, history, fileIDs) => (
  dispatch
) => {
  const { expandedFileIDs } = parseChangesetPath(location.pathname)
  const expandedBefore = expandedFileIDs.size
  const newExpandedFileIDs = expandedFileIDs.merge(fileIDs)
  if (newExpandedFileIDs.size === expandedBefore) return
  const linkPath = generateLinkPath({
    location,
    match,
    expandedFileIDs: newExpandedFileIDs,
  })
  console.error("expandFiles", { expandedFileIDs, fileIDs, linkPath })
  history.replace(linkPath)
}

export const collapseFiles = (location, match, history, fileIDs) => (
  dispatch
) => {
  const { expandedFileIDs } = parseChangesetPath(location.pathname)
  const linkPath = generateLinkPath({
    location,
    match,
    expandedFileIDs: expandedFileIDs.subtract(fileIDs),
  })
  console.error("collapseFiles", { expandedFileIDs, fileIDs, linkPath })
  history.replace(linkPath)
}
