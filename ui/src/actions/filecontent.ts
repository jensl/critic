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

import { assertNotNull, assertTrue } from "../debug"
import { expectStatuses, fetch, withParameters } from "../resources"
import { AsyncThunk } from "../state"
import FileContent from "../resources/filecontent"
import { CommitID, FileID, RepositoryID } from "../resources/types"
import { sleep } from "../utils/Functions"

/*
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
*/

type Params = {
  repository: RepositoryID
  commit: CommitID
  file: FileID
  first?: number
  last?: number
}

export const loadFileContent = (
  repositoryID: RepositoryID,
  commitID: CommitID,
  fileID: FileID,
  first: number | null = null,
  last: number | null = null,
): AsyncThunk<FileContent> => async (dispatch) => {
  const params: Params = {
    repository: repositoryID,
    commit: commitID,
    file: fileID,
  }
  if (first !== null) params.first = first
  if (last !== null) params.last = last

  let delay = 200

  while (true) {
    const { status, updates } = await dispatch(
      fetch("filecontents", withParameters(params), expectStatuses(200, 202)),
    )

    if (status === 202) {
      await sleep(delay)
      delay = Math.min(delay * 2, 1000)
      continue
    }

    assertNotNull(updates)

    const fileContents = updates.get("filecontents") as FileContent[]

    assertNotNull(fileContents)
    assertTrue(fileContents.length === 1)

    return fileContents[0]
  }
}
