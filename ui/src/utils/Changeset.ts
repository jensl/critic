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

import { Location } from "history"
import { match } from "react-router"

import { FileID, ChangesetID, ReviewID } from "../resources/types"
import Review from "../resources/review"
import Repository from "../resources/repository"
import Commit from "../resources/commit"
import Changeset, { CompletionLevel } from "../resources/changeset"
import { Channel } from "./WebSocket"
import { assertEqual } from "../debug"
import { AsyncThunk } from "../state"

const SHA1 = "[^.:]+"

const changesetIdentifier = [
  String.raw`(\d+)`,
  String.raw`by-sha1/(${SHA1})?\.\.(${SHA1})`,
  String.raw`by-sha1/(${SHA1})`,
  "automatic/(everything|reviewable|pending|relevant)",
].join("|")

const expandedFiles = String.raw`(?:(\d+_\d+(?:,\d+_\d+)*)|(\d+(?:,\d+)*))`

const pathRegexp = new RegExp(
  String.raw`/changeset/(?:${changesetIdentifier})(?:/expand:${expandedFiles})?$`,
)

const expandedFilesRegexp = new RegExp(String.raw`/expand:${expandedFiles}$`)

type Pathname = { pathname: string }

export const parseExpandedFiles = ({
  pathname,
}: Pathname): ReadonlySet<FileID | string> => {
  const match = expandedFilesRegexp.exec(pathname)
  if (!match) return new Set()
  const [, parentAndFileIDs, fileIDs] = match
  if (parentAndFileIDs) return new Set(parentAndFileIDs.split(","))
  return new Set(fileIDs.split(",").map((fileID) => parseInt(fileID, 10)))
}

export const pathWithExpandedFiles = (
  { pathname }: Pathname,
  expandedFileIDs: Iterable<FileID | string>,
) => {
  pathname = pathname.replace(expandedFilesRegexp, "")
  const fileIDs = [...expandedFileIDs]
  if (fileIDs.length > 0) {
    fileIDs.sort()
    pathname += `/expand:${fileIDs.join(",")}`
  }
  return pathname
}

type ChangesetPathInfo = {
  changesetID: ChangesetID | null
  fromCommit: string | null
  toCommit: string | null
  singleCommit: string | null
  automatic: string | null
  expandedFileIDs: ReadonlySet<FileID | string>
}

export const parseChangesetPath = (path: string): ChangesetPathInfo | null => {
  const match = pathRegexp.exec(path)
  if (!match) return null
  const [
    changesetID,
    fromCommit,
    toCommit,
    singleCommit,
    automatic,
    parentAndFileIDs,
    fileIDs,
  ] = match.slice(1)
  return {
    changesetID: changesetID ? parseInt(changesetID, 10) : null,
    fromCommit: fromCommit || null,
    toCommit: toCommit || null,
    singleCommit: singleCommit || null,
    automatic: automatic || null,
    expandedFileIDs: parentAndFileIDs
      ? new Set(parentAndFileIDs.split(","))
      : fileIDs
      ? new Set(fileIDs.split(",").map((fileID) => parseInt(fileID, 10)))
      : new Set(),
  }
}

export type ChangesetRouteParams = {
  dashboardCategory: string
  reviewID: string
  repository: string
}

type GenerateLinkPathProps = {
  location?: Location
  match?: match<ChangesetRouteParams>
  changesetID?: ChangesetID | null
  fromCommit?: string | null
  toCommit?: string | null
  singleCommit?: string | null
  automatic?: string | null
  review?: Review | { id: ReviewID } | null
  repository?: Repository | { name: string } | null
  expandedFileIDs?: ReadonlySet<FileID | string>
}

export const generateLinkPath = ({
  location,
  match,
  changesetID,
  fromCommit,
  toCommit,
  singleCommit,
  automatic,
  review,
  repository,
  expandedFileIDs,
}: GenerateLinkPathProps) => {
  const ref = (commit: string | Commit) => {
    if (typeof commit === "string") return commit
    return commit.sha1
  }
  const basePath = () => {
    if (match) {
      const { dashboardCategory = null } = match.params
      if (dashboardCategory !== null && review)
        return `/dashboard/${dashboardCategory}/review/${review.id}`
    }
    if (review) return `/review/${review.id}`
    if (repository) return `/repository/${repository.name}`
    throw Error("fail!")
  }
  const changesetPath = () => {
    if (typeof changesetID === "number") {
      return changesetID
    } else if (singleCommit) {
      return `by-sha1/${ref(singleCommit)}`
    } else if (fromCommit && toCommit) {
      return `by-sha1/${ref(fromCommit)}..${ref(toCommit)}`
    } else if (singleCommit) {
      return `by-sha1/..${ref(singleCommit)}`
    } else if (automatic) {
      return `automatic/${automatic}`
    } else {
      throw new Error()
    }
  }
  const expandedFiles = () => {
    if (expandedFileIDs && expandedFileIDs.size) {
      const sortedFileIDs = [...expandedFileIDs]
      sortedFileIDs.sort()
      return "/expand:" + sortedFileIDs.join(",")
    }
    return ""
  }

  if (location) {
    const params = parseChangesetPath(location.pathname)
    if (params) {
      if (params.changesetID && !changesetID) {
        changesetID = params.changesetID
      }
      if (params.fromCommit && !fromCommit) {
        fromCommit = params.fromCommit
      }
      if (params.toCommit && !toCommit) {
        toCommit = params.toCommit
      }
      if (params.singleCommit && !singleCommit) {
        singleCommit = params.singleCommit
      }
      if (params.automatic && !automatic) {
        automatic = params.automatic
      }
      if (params.expandedFileIDs && !expandedFileIDs) {
        expandedFileIDs = params.expandedFileIDs
      }
      if (match) {
        if (match.params.reviewID && !review) {
          review = { id: parseInt(match.params.reviewID, 10) }
        }
        if (match.params.repository && !repository) {
          repository = { name: match.params.repository }
        }
      }
    }
  }

  try {
    return `${basePath()}/changeset/${changesetPath()}${expandedFiles()}`
  } catch (error) {
    console.error({ error })
    return basePath()
  }
}

type WaitForCompletionLevelOptions = {
  completionLevel?: CompletionLevel
  timeout?: number
  changeset?: null | Changeset
}

export const waitForCompletionLevel = async (
  channel: Channel,
  {
    completionLevel = "full",
    timeout = 10000,
    changeset = null,
  }: WaitForCompletionLevelOptions,
) => {
  if (changeset && changeset.completionLevel.has(completionLevel)) return true

  try {
    await channel.waitFor(
      (message: any) => {
        console.log("waitForCompletionLevel predicate", {
          message,
          completionLevel,
        })
        return (
          message.action === "modified" &&
          message.updates.completion_level &&
          message.updates.completion_level.includes(completionLevel)
        )
      },
      { timeout },
    )
    return true
  } catch (error) {
    assertEqual(error, "timeout")
    return false
  }
}
