/*
 * Copyright 2018 the Critic contributors, Opera Software ASA
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

import Resource, { withArgument } from "../resources"
import { UserID, RepositoryID, RepositoryFilterID } from "../resources/types"
import { AsyncThunk } from "../state"
import { RequestParams } from "../utils/Fetch.types"
import RepositoryFilter from "../resources/repositoryfilter"

export const loadRepositoryFilters = ({
  userID = null,
  repositoryID = null,
}: {
  userID?: UserID | null
  repositoryID?: RepositoryID | null
}): AsyncThunk<RepositoryFilter[]> => async (dispatch) => {
  const parameters: RequestParams = {}
  if (userID !== null) parameters.user = userID
  if (repositoryID !== null) parameters.repository = repositoryID
  const { primary } = await dispatch(
    Resource.fetch("repositoryfilters", parameters),
  )
  return primary
}

export const createRepositoryFilter = (
  repositoryID: RepositoryID,
  type: "reviewer" | "watcher" | "ignored",
  path: string,
  delegateIDs: Iterable<number>,
) =>
  Resource.create(
    "repositoryfilters",
    { type, path, delegates: [...delegateIDs] },
    { params: { repository: repositoryID } },
  )

export const deleteRepositoryFilter = (filterID: RepositoryFilterID) =>
  Resource.delete("repositoryfilters", withArgument(filterID))
