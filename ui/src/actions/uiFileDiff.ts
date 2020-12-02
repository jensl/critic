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

import { useHistory, useLocation, useRouteMatch, match } from "react-router"

import { showToast } from "./uiToast"
import { toggleReviewableFileChange } from "./reviewableFilechange.js"
import {
  parseChangesetPath,
  generateLinkPath,
  ChangesetRouteParams,
  parseExpandedFiles,
  pathWithExpandedFiles,
} from "../utils/Changeset"
import { FileID } from "../resources/types"
import { useDispatch } from "../store"
import { Thunk } from "../state"
import { assertNotNull } from "../debug"
import { filteredSet, mergedSets } from "../utils/Functions"

/*const isInView = (inView, fileKey, part) =>
  inView.has(`file:${fileKey}:${part}`)

export const collapseFile = (
  location,
  match,
  history,
  expandedFileIDs,
  fileKey,
  reviewableFileChanges,
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
  var { expandedFileIDs } = parseChangesetPath(location.pathname)

  const session = state.resource.sessions.get("current")
  const signedInUser = state.resource.users.byID.get(
    session && session.user,
    null,
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
      }),
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
          }),
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
}*/

type Location = ReturnType<typeof useLocation>
type History = ReturnType<typeof useHistory>

export const expandFiles = (
  location: Location,
  history: History,
  fileIDs: Iterable<FileID | string>,
): Thunk<void> => (dispatch) => {
  const currentExpandedFileIDs = parseExpandedFiles(location)
  const newExpandedFileIDs = mergedSets(currentExpandedFileIDs, fileIDs)
  console.log({ fileIDs, currentExpandedFileIDs, newExpandedFileIDs })
  history.replace(pathWithExpandedFiles(location, newExpandedFileIDs))
}

export const collapseFiles = (
  location: Location,
  history: History,
  fileIDs: Iterable<FileID | string>,
): Thunk<void> => (dispatch) => {
  const currentExpandedFileIDs = parseExpandedFiles(location)
  const excludeFileIDs = new Set(fileIDs)
  const newExpandedFileIDs = filteredSet(
    currentExpandedFileIDs,
    (fileID) => !excludeFileIDs.has(fileID),
  )
  console.log({ fileIDs, currentExpandedFileIDs, newExpandedFileIDs })
  history.replace(pathWithExpandedFiles(location, newExpandedFileIDs))
}

export const useExpandedFiles = () => {
  const dispatch = useDispatch()
  const location = useLocation()
  const match = useRouteMatch()
  const history = useHistory()

  return {
    expandFiles: (fileIDs: Iterable<FileID | string>) =>
      dispatch(expandFiles(location, history, fileIDs)),
    collapseFiles: (fileIDs: Iterable<FileID | string>) =>
      dispatch(collapseFiles(location, history, fileIDs)),
  }
}
