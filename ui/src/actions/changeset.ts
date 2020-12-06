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
import { fetch, handleError, include, withParameters } from "../resources"
import Changeset, { CompletionLevel } from "../resources/changeset"
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
import { InvalidItem, Action, AutomaticMode, SET_AUTOMATIC_CHANGESET } from "."
import { waitForCompletionLevel } from "../utils/Changeset"

const setAutomaticChangeset = (
  reviewID: ReviewID,
  automatic: AutomaticMode,
  changesetID: ChangesetID,
): Action => ({
  type: SET_AUTOMATIC_CHANGESET,
  reviewID,
  automatic,
  changesetID,
})

type LoadFileDiffsForChangesetOptions = {
  reviewID?: number
  repositoryID?: number
}

const loadFileDiffsForChangeset = (
  changeset: Changeset,
  channel: Channel | null,
  { reviewID, repositoryID }: LoadFileDiffsForChangesetOptions,
): AsyncThunk<void> => async (dispatch, getState) => {
  console.log("loadFileDiffsForChangeset", { changeset })

  if (!changeset.completionLevel.has("full")) {
    assertNotNull(channel)
    while (!(await waitForCompletionLevel(channel, { changeset }))) {
      // Then check what the changeset's current completion level is. This is
      // done to avoid a race where we begin to listen for updates just after an
      // update.
      const { status } = await dispatch(
        fetchJSON({
          path: `changesets/${changeset.id}`,
          params: {
            fields: "id",
            only_if_complete: "full",
          },
          expectStatus: [200, 202],
        }),
      )

      if (status === 200) break
    }
  }

  console.log("loadFileDiffsForChangeset", { changeset })

  if (channel !== null) channel.close()

  const { files } = changeset
  assertNotNull(files)

  const filediffs = getState().resource.filediffs
  const neededFilediffs = files.filter(
    (fileID) => !filediffs.has(`${changeset.id}:${fileID}`),
  )

  if (neededFilediffs.length === 0) return

  const chunkCount = Math.ceil(neededFilediffs.length / 10)
  const chunkSize = Math.ceil(neededFilediffs.length / chunkCount)
  const promises = []

  for (let offset = 0; offset < neededFilediffs.length; offset += chunkSize) {
    const fileIDs = neededFilediffs.slice(offset, offset + chunkSize)
    promises.push(
      dispatch(
        loadFileDiffs(fileIDs, {
          changeset,
          reviewID,
          repositoryID,
        }),
      ),
    )
  }

  await Promise.all(promises)
}

type RepositoryIDParam = { repositoryID: RepositoryID }
type ReviewIDParam = { reviewID: ReviewID }
type ContextIDParam = RepositoryIDParam | ReviewIDParam

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

type SingleCommitRef = {
  singleCommitRef: string
}
type CommitRangeRefs = {
  fromCommitRef?: string
  toCommitRef: string
}
type CommitRefs = { refs: SingleCommitRef | CommitRangeRefs }

type LoadChangesetBySHA1Params = ContextIDParam & CommitRefs

export const loadChangesetBySHA1 = ({
  refs,
  ...context
}: LoadChangesetBySHA1Params): AsyncThunk<void> => async (
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
      return
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
    return
  }

  const changeset = primary[0]

  if (!changeset) return

  if ("singleCommitRef" in refs) {
    const { singleCommitRef } = refs
    commitRefs.set(commitRefKey(singleCommitRef), changeset.toCommit)
  } else {
    const { fromCommitRef, toCommitRef } = refs
    if (fromCommitRef)
      commitRefs.set(commitRefKey(fromCommitRef), changeset.fromCommit)
    commitRefs.set(commitRefKey(toCommitRef), changeset.toCommit)
  }

  dispatch(commitRefsUpdate(commitRefs))

  await dispatch(finishChangeset(changeset, context))
}

const finishChangeset = (
  changeset: Changeset,
  context: ContextIDParam,
): AsyncThunk<void> => async (dispatch) => {
  const channel = !changeset.completionLevel.has("full")
    ? await dispatch(Channel.subscribe(`changesets/${changeset.id}`))
    : null

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

    dispatch(
      loadChangesetByID(changeset.id, {
        ...context,
        onlyIfComplete: "structure",
        retryCount: 1,
        channel,
      }),
    )
  } else {
    dispatch(loadFileDiffsForChangeset(changeset, channel, context))
  }
}

type LoadChangesetByIDOptions = {
  reviewID?: ReviewID
  repositoryID?: RepositoryID
  onlyIfComplete?: false | CompletionLevel
  retryCount?: number
  channel?: any
}

export const loadChangesetByID = (
  changesetID: ChangesetID,
  {
    reviewID,
    repositoryID,
    onlyIfComplete = false,
    retryCount = 0,
    channel = null,
  }: LoadChangesetByIDOptions = {},
): AsyncThunk<Changeset | null> => async (dispatch) => {
  if (channel === null)
    channel = await dispatch(Channel.subscribe(`changesets/${changesetID}`))

  const options = Changeset.requestOptions(
    {
      byID: changesetID,
    },
    {
      reviewID,
      repositoryID,
      onlyIfComplete,
    },
  )

  console.log({ options })

  const { primary, status } = await dispatch(fetch("changesets", ...options))

  if (status === "delayed") {
    await waitForCompletionLevel(channel, {
      completionLevel: onlyIfComplete || "structure",
      timeout: Math.min(10000, 1000 + 500 * retryCount),
    })

    retryCount += 1

    return await dispatch(
      loadChangesetByID(changesetID, {
        reviewID,
        repositoryID,
        onlyIfComplete,
        retryCount,
        channel,
      }),
    )
  }

  const changeset = primary[0]

  if (!changeset.completionLevel.has("structure")) {
    await waitForCompletionLevel(channel, {
      completionLevel: onlyIfComplete || "structure",
      timeout: Math.max(10000, 1000 + 500 * retryCount),
    })

    retryCount += 1

    return await dispatch(
      loadChangesetByID(changesetID, {
        reviewID,
        repositoryID,
        onlyIfComplete: "structure",
        retryCount,
        channel,
      }),
    )
  }

  dispatch(
    loadFileDiffsForChangeset(changeset, channel, {
      reviewID,
      repositoryID,
    }),
  )

  return changeset
}

export const loadAutomaticChangeset = (
  automatic: AutomaticMode,
  reviewID: ReviewID,
) => async (dispatch: Dispatch): Promise<Changeset | null> => {
  console.error({ automatic, reviewID })

  const { primary } = await dispatch(
    fetch(
      "changesets",
      ...Changeset.requestOptions({ automatic }, { reviewID }),
    ),
  )

  const changeset = primary[0]
  const channel = !changeset.completionLevel.has("full")
    ? await dispatch(Channel.subscribe(`changesets/${changeset.id}`))
    : null

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

  dispatch(loadFileDiffsForChangeset(changeset, channel, { reviewID }))

  return changeset
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
