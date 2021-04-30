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

import { commitRefsUpdate } from "./commit"
import { loadFileDiffs } from "./filediff"
import { assertString, assertNotNull, assertTrue } from "../debug"
import {
  fetch,
  fetchOne,
  handleError,
  include,
  includeFields,
  withArgument,
  withParameters,
} from "../resources"
import Changeset, { CompletionLevel, Progress } from "../resources/changeset"
import { fetchJSON } from "../utils/Fetch"
import { Channel } from "../utils/WebSocket"
import { AsyncThunk, Dispatch, GetState } from "../state"
import MergeAnalysis from "../resources/mergeanalysis"
import {
  ReviewID,
  ChangesetID,
  CommitID,
  RepositoryID,
} from "../resources/types"
import {
  InvalidItem,
  Action,
  AutomaticMode,
  SET_AUTOMATIC_CHANGESET,
  AutomaticChangesetImpossible,
  AutomaticChangesetEmpty,
} from "."
import { CommitRefs, waitForCompletionLevel } from "../utils/Changeset"
import { sortedBy } from "../utils"

const WAIT_FOR_COMPLETION_LEVEL_TIMEOUT = 60000

const setAutomaticChangeset = (
  reviewID: ReviewID,
  automatic: AutomaticMode,
  changesetID:
    | ChangesetID
    | AutomaticChangesetEmpty
    | AutomaticChangesetImpossible,
): Action => ({
  type: SET_AUTOMATIC_CHANGESET,
  reviewID,
  automatic,
  changesetID,
})

const FILEDIFFS_LIMIT = 50

export const loadFileDiffsForChangeset = (
  changesetID: ChangesetID,
  reviewID: ReviewID | undefined,
): AsyncThunk<void> => async (dispatch, getState) => {
  let changeset = getState().resource.changesets.byID.get(changesetID)

  console.log("loadFileDiffsForChangeset", { changeset })

  assertNotNull(changeset)
  assertTrue(changeset.completionLevel.has("full"))

  const { files } = changeset
  assertNotNull(files)

  const filediffs = getState().resource.filediffs
  const filesByID = getState().resource.files.byID

  const neededFilediffs = sortedBy(
    files.filter((fileID) => !filediffs.has(`${changesetID}:${fileID}`)),
    (fileID) => filesByID.get(fileID)?.path ?? fileID,
  )

  if (neededFilediffs.length === 0) return

  console.log({ neededFilediffs })

  const chunkCount = Math.ceil(neededFilediffs.length / 50)
  const chunkSize = Math.ceil(neededFilediffs.length / chunkCount)
  const promises = []

  for (let offset = 0; offset < neededFilediffs.length; offset += chunkSize) {
    const fileIDs = neededFilediffs.slice(offset, offset + chunkSize)
    promises.push(
      dispatch(
        loadFileDiffs(fileIDs, {
          changeset,
          reviewID,
          limited: neededFilediffs.length > FILEDIFFS_LIMIT,
        }),
      ),
    )
  }

  await Promise.all(promises)
}

type RepositoryIDParam = { repositoryID: RepositoryID }
type ReviewIDParam = { reviewID: ReviewID }
export type ContextIDParam = RepositoryIDParam | ReviewIDParam

const isRepositoryID = (
  context: ContextIDParam,
): context is RepositoryIDParam => "repositoryID" in context

const isReviewID = (context: ContextIDParam): context is ReviewIDParam =>
  "reviewID" in context

const getRepositoryID = (getState: GetState, context: ContextIDParam) => {
  if (isReviewID(context)) {
    const review = getState().resource.reviews.get(context.reviewID)
    assertNotNull(review)
    return review.repository
  } else {
    return context.repositoryID
  }
}

type LoadChangesetBySHA1Params = ContextIDParam & { refs: CommitRefs }

export const loadChangesetBySHA1 = ({
  refs,
  ...context
}: LoadChangesetBySHA1Params): AsyncThunk<Changeset | null> => async (
  dispatch,
  getState,
) => {
  const repositoryID = getRepositoryID(getState, context)

  const byCommits =
    "singleCommitRef" in refs
      ? { singleCommit: refs.singleCommitRef }
      : { fromCommit: refs.fromCommitRef, toCommit: refs.toCommitRef }

  const { primary, status, error } = await dispatch(
    fetch(
      "changesets",
      ...Changeset.requestOptions(byCommits, context),
      handleError("MERGE_COMMIT", () => (console.log("Merge commit!"), false)),
    ),
  )

  const commitRefKey = (ref: string) => `${repositoryID}:${ref}`
  const commitRefs = new Map<string, CommitID | InvalidItem>()

  if (status === "notfound") {
    if (error!.code === "MERGE_COMMIT") {
      assertTrue("singleCommitRef" in refs)
      await dispatch(loadMergeAnalysis(refs.singleCommitRef, { repositoryID }))
      return null
    }
    if ("singleCommitRef" in refs) {
      const { singleCommitRef } = refs
      commitRefs.set(
        commitRefKey(singleCommitRef),
        new InvalidItem(singleCommitRef),
      )
    } else {
      const { fromCommitRef, toCommitRef } = refs
      if (fromCommitRef)
        commitRefs.set(
          commitRefKey(fromCommitRef),
          new InvalidItem(fromCommitRef),
        )
      commitRefs.set(commitRefKey(toCommitRef), new InvalidItem(toCommitRef!))
    }

    dispatch(commitRefsUpdate(commitRefs))
    return null
  }

  const changeset = primary[0]

  if (!changeset) return null

  if ("singleCommitRef" in refs) {
    const { singleCommitRef } = refs
    commitRefs.set(commitRefKey(singleCommitRef), changeset.toCommit)
  } else {
    const { fromCommitRef, toCommitRef } = refs
    if (fromCommitRef && changeset.fromCommit)
      commitRefs.set(commitRefKey(fromCommitRef), changeset.fromCommit)
    commitRefs.set(commitRefKey(toCommitRef), changeset.toCommit)
  }

  dispatch(commitRefsUpdate(commitRefs))

  //await dispatch(finishChangeset(changeset, context))

  return changeset
}

const finishChangeset = (
  changeset: Changeset,
  context: ContextIDParam,
): AsyncThunk<void> => async (dispatch) => {
  if (changeset.completionLevel.has("full")) return

  const completionLevel = !changeset.completionLevel.has("structure")
    ? "structure"
    : "full"

  const channel = await dispatch(
    Channel.monitorChangeset(changeset.id, completionLevel),
  )

  if (channel) {
    console.log("finishChangeset", { channel, waitingFor: completionLevel })

    await waitForCompletionLevel(channel, {
      completionLevel: completionLevel,
      timeout: WAIT_FOR_COMPLETION_LEVEL_TIMEOUT,
      changeset,
    })
  }

  dispatch(
    loadChangesetByID(changeset.id, {
      ...context,
      onlyIfComplete: completionLevel,
      retryCount: 1,
      channel,
    }),
  )
}

type LoadChangesetByIDOptions = {
  reviewID?: ReviewID
  onlyIfComplete?: false | CompletionLevel
}

export const loadChangesetByID = (
  changesetID: ChangesetID,
  { reviewID, onlyIfComplete = false }: LoadChangesetByIDOptions = {},
): AsyncThunk<Changeset | null> => async (dispatch) => {
  const options = Changeset.requestOptions(
    {
      byID: changesetID,
    },
    {
      reviewID,
      onlyIfComplete,
    },
  )

  const { primary, status } = await dispatch(fetch("changesets", ...options))

  if (status === "delayed") return null

  return primary[0]
}

export const loadChangesetStateByID = (
  changesetID: ChangesetID,
): AsyncThunk<[ReadonlySet<CompletionLevel>, Progress | null]> => async (
  dispatch,
) => {
  const changeset = await dispatch(
    fetchOne(
      "changesets",
      withArgument(changesetID),
      includeFields("changesets", ["completion_level", "progress"]),
    ),
  )
  return [changeset.completionLevel, changeset.progress]
}

export const loadAutomaticChangeset = (
  automatic: AutomaticMode,
  reviewID: ReviewID,
) => async (dispatch: Dispatch): Promise<Changeset | null> => {
  try {
    const { primary } = await dispatch(
      fetch(
        "changesets",
        ...Changeset.requestOptions({ automatic }, { reviewID }),
        handleError("AUTOMATIC_CHANGESET_EMPTY", (error) => {
          throw new AutomaticChangesetEmpty(error.message)
        }),
        handleError("AUTOMATIC_CHANGESET_IMPOSSIBLE", (error) => {
          throw new AutomaticChangesetImpossible(error.message)
        }),
      ),
    )

    const changeset = primary[0]
    const channel = !changeset.completionLevel.has("full")
      ? await dispatch(Channel.monitorChangeset(changeset.id, "full"))
      : undefined

    dispatch(setAutomaticChangeset(reviewID, automatic, changeset.id))

    if (!changeset.completionLevel.has("structure")) {
      assertNotNull(channel)

      // Use a short (200 ms) timeout here, since there's a race between our
      // initial check and our subscription to status update message. This race is
      // sort of unavoidable, since we don't know the changeset id before the
      // initial check.
      await waitForCompletionLevel(channel, {
        completionLevel: "structure",
        timeout: 200,
        changeset,
      })

      return await dispatch(
        loadChangesetByID(changeset.id, {
          reviewID,
          onlyIfComplete: "structure",
          retryCount: 1,
          channel,
        }),
      )
    }

    return changeset
  } catch (error) {
    if (
      error instanceof AutomaticChangesetEmpty ||
      error instanceof AutomaticChangesetImpossible
    ) {
      dispatch(setAutomaticChangeset(reviewID, automatic, error))
      return null
    }
    throw error
  }
}

export const loadMergeAnalysis = (
  commit: number | string,
  {
    retryCount = 0,
    ...context
  }: ContextIDParam & {
    retryCount?: number
  },
): AsyncThunk<MergeAnalysis | null> => async (dispatch, getState) => {
  const { status, primary, updates } = await dispatch(
    fetch(
      "mergeanalyses",
      withParameters({
        commit,
        repository: isRepositoryID(context) ? context.repositoryID : undefined,
        review: isReviewID(context) ? context.reviewID : undefined,
      }),
    ),
  )

  if (status === "delayed")
    return await new Promise<MergeAnalysis | null>((resolve, reject) => {
      setTimeout(async () => {
        resolve(
          await dispatch(
            loadMergeAnalysis(commit, {
              ...context,
              retryCount: retryCount + 1,
            }),
          ),
        )
      }, 1000 + 1000 * retryCount)
    })

  const mergeAnalysis = primary[0]

  if (!mergeAnalysis) return null

  if (typeof commit === "string")
    dispatch(
      commitRefsUpdate(
        new Map<string, CommitID>([
          [
            `${getRepositoryID(getState, context)}:${commit}`,
            mergeAnalysis.merge,
          ],
        ]),
      ),
    )

  if (mergeAnalysis.conflictResolutions !== null) {
    for (const changeset of updates?.get("changesets") || []) {
      if (changeset.id !== mergeAnalysis.conflictResolutions) continue
      await dispatch(finishChangeset(changeset, context))
    }
  }

  return mergeAnalysis
}
