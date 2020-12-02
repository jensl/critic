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

import { fetch, withParameters } from "../resources"
import Tree from "../resources/tree"
import { RepositoryID, CommitID } from "../resources/types"
import { AsyncThunk } from "../state"

export const loadTree = (
  repositoryID: RepositoryID,
  commitID: CommitID,
  path: string = "/",
): AsyncThunk<Tree | null> => async (dispatch) => {
  const { primary } = await dispatch(
    fetch(
      "trees",
      withParameters({
        repository: repositoryID,
        commit: commitID,
        path,
      }),
    ),
  )

  if (!primary.length) return null
  const tree = primary[0]

  dispatch({
    type: "TREES_UPDATE",
    repositoryID,
    commitID,
    path,
    sha1: tree.sha1,
  })

  return tree
}
