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

import { createSelector } from "reselect"

import { State } from "../state"
import File from "../resources/file"
import { FileID } from "../resources/types"
import { map } from "../utils"

const getFilesByID = (state: State) => state.resource.files.byID
const getSelectedFolderPaths = (state: State) =>
  state.ui.rest.fileTreeView.selectedFolders
const getLockedFolderPaths = (state: State) =>
  state.ui.rest.fileTreeView.lockedFolders
const getSelectedFileIDs = (state: State) =>
  state.ui.rest.fileTreeView.selectedFileIDs
const getLockedFileIDs = (state: State) =>
  state.ui.rest.fileTreeView.lockedFileIDs

export const getNewSelectedFolderPaths = createSelector(
  getSelectedFolderPaths,
  getLockedFolderPaths,
  (selectedFolders, lockedFolders) => selectedFolders.subtract(lockedFolders)
)

export const getNewSelectedFileIDs = createSelector(
  getSelectedFileIDs,
  getLockedFileIDs,
  (selectedFileIDs, lockedFileIDs) => selectedFileIDs.subtract(lockedFileIDs)
)

const fileIDsToPaths = (
  filesByID: ReadonlyMap<FileID, File>,
  fileIDs: ReadonlySet<FileID>
): ReadonlySet<string> =>
  new Set(
    map(fileIDs, (fileID) => filesByID.get(fileID))
      .filter((value): value is File => !!value)
      .map((file) => file.path)
  )

export const getSelectedFilePaths = createSelector(
  getFilesByID,
  getSelectedFileIDs,
  fileIDsToPaths
)

export const getLockedFilePaths = createSelector(
  getFilesByID,
  getLockedFileIDs,
  fileIDsToPaths
)

export const getNewSelectedFilePaths = createSelector(
  getFilesByID,
  getNewSelectedFileIDs,
  fileIDsToPaths
)

export const getNewFilterPaths = createSelector(
  getNewSelectedFolderPaths,
  getNewSelectedFilePaths,
  (folderPaths, filePaths): readonly string[] => {
    if (folderPaths.has("/")) {
      return ["/"]
    }
    const allPaths = [...folderPaths.map((path) => path + "/"), ...filePaths]
    allPaths.sort()
    return allPaths.reduce((filteredPaths: string[], path) => {
      if (filteredPaths.length) {
        const previousPath = filteredPaths[filteredPaths.length - 1]
        if (
          previousPath.endsWith("/") &&
          (previousPath === "/" || path.startsWith(previousPath))
        ) {
          return filteredPaths
        }
      }
      filteredPaths.push(path)
      return filteredPaths
    }, [])
  }
)
