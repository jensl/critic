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

import { fetch, withArguments } from "../resources"
import { Channel } from "../utils/WebSocket"
import Changeset from "../resources/changeset"
import { AsyncThunk } from "../state"
import { assertNotNull } from "../debug"
import { ChangesetID, FileID, ReviewID } from "../resources/types"
import { waitForCompletionLevel } from "../utils/Changeset"
import { withData } from "../resources/requestoptions"
import { filteredSet } from "../utils/Functions"

type LoadFileDiffOptions = {
  changeset?: Changeset
  changesetID?: ChangesetID
  reviewID?: ReviewID
  limited?: boolean
}

export const loadFileDiff = (
  fileID: FileID,
  options: LoadFileDiffOptions,
): AsyncThunk<void> => loadFileDiffs([fileID], options)

const FILEDIFFS_LIMIT = 50

export const loadFileDiffs = (
  fileIDs: Iterable<FileID>,
  { changeset, changesetID, reviewID, limited = false }: LoadFileDiffOptions,
): AsyncThunk<void> => async (dispatch, getState) => {
  let isComplete = false

  if (changeset) {
    changesetID = changeset.id
    isComplete = changeset.completionLevel.has("full")
  }

  const filediffs = getState().resource.filediffs
  const neededFileIDs = filteredSet(
    fileIDs,
    (fileID) => !filediffs.get(`${changesetID}:${fileID}`)?.macroChunks,
  )

  console.log({ fileIDs, neededFileIDs })

  if (neededFileIDs.size === 0 || neededFileIDs.size > FILEDIFFS_LIMIT) return

  const { status, primary } = await dispatch(
    fetch(
      "filediffs",
      withArguments([...neededFileIDs]),
      withData({
        changeset,
        changesetID,
        reviewID,
        limited,
      }),
    ),
  )
}
