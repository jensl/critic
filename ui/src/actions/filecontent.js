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

import { dataUpdate } from "./data"
import { assertNotNull } from "../debug"
import { handleJSONResponse } from "../resources"
import { fetchJSON } from "../utils/Fetch"

export const FILECONTENT_UPDATE = "FILECONTENT_UPDATE"
export const filecontentUpdate = ({
  repositoryID,
  commitID,
  fileID,
  path,
  changesetID,
  chunkIndex,
  first,
  last,
  lines,
}) => ({
  type: FILECONTENT_UPDATE,
  repositoryID,
  commitID,
  fileID,
  path,
  changesetID,
  chunkIndex,
  first,
  last,
  lines,
})

export const loadFileContent = ({
  repositoryID = null,
  commitID = null,
  changesetID = null,
  path = null,
  fileID = null,
  first = null,
  last = null,
  chunkIndex = null,
  delay = 200,
}) => async (dispatch, getState) => {
  assertNotNull(repositoryID)
  assertNotNull(commitID)
  path = path || getState().resource.files.byID.get(fileID).path
  const params = {
    repository: repositoryID,
    commit: commitID,
    file: fileID !== null ? fileID : path,
  }
  if (first !== null) params.first = first
  if (last !== null) params.last = last
  const { status, updates } = dispatch(
    handleJSONResponse(
      await dispatch(
        fetchJSON({
          path: "filecontents",
          params,
          include: ["files"],
          expectStatus: [200, 202],
        })
      )
    )
  )

  if (status === 202) {
    setTimeout(
      () =>
        dispatch(
          loadFileContent({
            repositoryID,
            commitID,
            path,
            fileID,
            first,
            last,
            changesetID,
            chunkIndex,
            delay: Math.min(delay * 2, 1000),
          })
        ),
      delay
    )
  } else {
    const fileContent = updates.get("filecontents").first()
    dispatch(
      filecontentUpdate({
        repositoryID,
        commitID,
        fileID: fileContent.file || fileID,
        path,
        changesetID,
        chunkIndex,
        first,
        last,
        lines: fileContent.lines,
      })
    )
  }
}
