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

import { assertNotNull } from "../debug"
import { fetch, include, withArgument, withParameters } from "../resources"
import { Dispatch, GetState } from "../state"
import { InvalidItem, CommitRefsUpdateAction, COMMIT_REFS_UPDATE } from "."
import { CommitID, RepositoryID, ReviewID } from "../resources/types"

export const commitRefsUpdate = (
  refs: Map<string, CommitID | InvalidItem>,
): CommitRefsUpdateAction => ({
  type: COMMIT_REFS_UPDATE,
  refs,
})

type FetchParamsParams = {
  commitID?: null | number
  ref?: null | string
  reviewID?: null | number
  repositoryID?: null | number
  description?: null | "default"
}

const fetchParams = ({
  commitID = null,
  ref = null,
  reviewID = null,
  repositoryID = null,
  description = null,
}: FetchParamsParams) => {
  const options = []
  if (commitID !== null) options.push(withArgument(commitID))
  if (ref !== null) options.push(withParameters({ ref }))
  if (reviewID !== null) {
    options.push(withParameters({ review: String(reviewID) }))
  } else {
    assertNotNull(repositoryID)
    options.push(withParameters({ repository: String(repositoryID) }))
  }
  if (description !== null) {
    options.push(withParameters({ description }))
    options.push(include("branches"))
  }
  return options
}

type ReviewIDOption = { reviewID: ReviewID }
type RepositoryIDOption = { repositoryID: RepositoryID }
type DescriptionOption = { description?: null | "default" }

type LoadCommitByIDOptions = (ReviewIDOption | RepositoryIDOption) &
  DescriptionOption

export const loadCommitByID = (
  commitID: CommitID,
  options: LoadCommitByIDOptions,
) => async (dispatch: Dispatch, getState: GetState) => {
  const commit = getState().resource.commits.byID.get(commitID)

  if (!commit || options.description === "default") {
    const { primary } = await dispatch(
      fetch("commits", ...fetchParams({ commitID, ...options })),
    )

    if (!primary) return

    const commit = primary[0]

    const hasRepositoryID = (
      options: LoadCommitByIDOptions,
    ): options is RepositoryIDOption => "repositoryID" in options

    if (hasRepositoryID(options)) {
      dispatch(
        commitRefsUpdate(
          new Map<string, CommitID | InvalidItem>([
            [`${options.repositoryID}:${commit.sha1}`, commit.id],
          ]),
        ),
      )
    }
  }
}

export const resolveRef = (
  ref: string,
  repositoryID: RepositoryID,
  description: "default" | null = null,
) => async (dispatch: Dispatch, getState: GetState) => {
  const refKey = `${repositoryID}:${ref}`
  const commitID = getState().resource.extra.commitRefs.get(refKey)

  if (typeof commitID !== "number" || description !== null) {
    const { primary } = await dispatch(
      fetch("commits", ...fetchParams({ ref, repositoryID, description })),
    )

    if (!primary) return

    const commit = primary[0]
    const refs = new Map<string, CommitID | InvalidItem>()
    refs.set(refKey, commit.id)
    if (ref !== commit.sha1)
      refs.set(`${repositoryID}:${commit.sha1}`, commit.id)
    dispatch(commitRefsUpdate(refs))
  }
}
