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
import Changeset from "../resources/changeset"
import Comment, { Location } from "../resources/comment"
import { getCommentsForReview } from "./review"
import { ChangesetID, FileID } from "../resources/types"
import { assertNotNull } from "../debug"
import { castImmutable } from "immer"
import { kDeletedLine, kInsertedLine } from "../resources/diffcommon"
import { any } from "../utils"

const getCommentLocations = (state: State) =>
  state.resource.extra.commentLocations
// const getActiveFile = (state: State) => state.ui.codeLines.anchorPartition
// const getAnchorLineID = (state: State) => state.ui.codeLines.anchorEntity
// const getFocusLineID = (state: State) => state.ui.codeLines.focusEntity

export const getFileDiffs = (state: State) => state.resource.filediffs

type ChangesetProp = { changeset: Changeset | null }
type ChangesetIDProp = { changesetID: ChangesetID }
type GetChangesetProps = ChangesetProp | ChangesetIDProp

const isChangesetProp = (props: GetChangesetProps): props is ChangesetProp =>
  "changeset" in props

export const getChangeset = (state: State, props: GetChangesetProps) =>
  isChangesetProp(props)
    ? props.changeset
    : state.resource.changesets.byID.get(props.changesetID)

type FileIDProp = { fileID: FileID }

export const getFileChange = (
  state: State,
  props: FileIDProp & GetChangesetProps,
) => {
  const changeset = getChangeset(state, props)
  if (!changeset) return null
  return state.resource.filechanges.get(`${changeset.id}:${props.fileID}`)
}

export const getFileDiff = (
  state: State,
  props: FileIDProp & GetChangesetProps,
) => {
  const changeset = getChangeset(state, props)
  if (!changeset) return null
  return state.resource.filediffs.get(`${changeset.id}:${props.fileID}`)
}

export type LineSideComments = {
  hasOpenIssues: boolean
  hasClosedIssues: boolean
  hasNotes: boolean
  comments: readonly Comment[]
}

export type LineComments = {
  oldSide: LineSideComments
  newSide: LineSideComments
}

export type ChunkComments = ReadonlyMap<string, LineComments>

type CommentsByLine = ReadonlyMap<string, readonly Comment[]>
type MutableCommentsByLine = Map<string, Comment[]>

export type CommentsByFileValue = {
  byLine: CommentsByLine
  byLinePrimary: CommentsByLine
  byChunk: readonly ChunkComments[]
  all: readonly Comment[]
}

type MutableCommentsByFileValue = {
  byLine: MutableCommentsByLine
  byLinePrimary: MutableCommentsByLine
  byChunk: ChunkComments[]
  all: Comment[]
}

export type CommentsByFile = ReadonlyMap<FileID, CommentsByFileValue>

type MutableCommentsByFile = Map<FileID, MutableCommentsByFileValue>

export type CommentsForChangeset = {
  inCommitMessage: readonly Comment[]
  byFile: CommentsByFile
}

const addComment = (
  byLine: Map<string, Comment[]>,
  location: Location,
  lineNumber: number,
  comment: Comment,
) => {
  const lineID = `${location.side!.charAt(0)}${lineNumber}`
  if (!byLine.has(lineID)) byLine.set(lineID, [])
  byLine.get(lineID)!.push(comment)
}

const hasOpenIssues = (comments: readonly Comment[]) =>
  any(
    comments,
    (comment) => comment.type === "issue" && comment.state === "open",
  )
const hasClosedIssues = (comments: readonly Comment[]) =>
  any(
    comments,
    (comment) => comment.type === "issue" && comment.state !== "open",
  )
const hasNotes = (comments: readonly Comment[]) =>
  any(comments, (comment) => comment.type === "note")

export const getCommentsForChangeset = createSelector(
  getCommentLocations,
  getCommentsForReview,
  getChangeset,
  getFileDiffs,
  (
    commentLocations,
    commentsForReview,
    changeset,
    fileDiffs,
  ): CommentsForChangeset => {
    const inCommitMessage: Comment[] = []
    const byFile: MutableCommentsByFile = new Map()
    const result = {
      inCommitMessage,
      byFile,
    }
    if (!changeset || !changeset.files) return result
    var commitID = null
    if (changeset.contributingCommits?.length === 1) {
      commitID = changeset.toCommit
    }
    for (const fileID of changeset.files) {
      byFile.set(fileID, {
        byLine: new Map(),
        byLinePrimary: new Map(),
        byChunk: [],
        all: [],
      })
    }
    for (const comment of commentsForReview) {
      const translatedLocation = commentLocations.get(
        `${changeset.id}:${comment.id}`,
      )
      if (!translatedLocation) continue
      if (translatedLocation.type === "commit-message") {
        if (translatedLocation.commit === commitID)
          inCommitMessage.push(comment)
        continue
      }
      // Not null since we've taken care of commit-message locations above.
      const fileID = translatedLocation.file
      assertNotNull(fileID)
      const translatedComment = Comment.new({
        ...comment.props,
        location: translatedLocation,
      })
      const byFileItem = byFile.get(fileID)
      if (!byFileItem) continue
      const { byLine, byLinePrimary, all } = byFileItem
      all.push(translatedComment)
      for (
        let lineNumber = translatedLocation.firstLine;
        lineNumber <= translatedLocation.lastLine;
        ++lineNumber
      )
        addComment(byLine, translatedLocation, lineNumber, translatedComment)
      addComment(
        byLinePrimary,
        translatedLocation,
        translatedLocation.lastLine,
        translatedComment,
      )
    }
    for (const fileID of changeset.files) {
      const { byLine, byLinePrimary, byChunk } = byFile.get(fileID)!
      const fileDiff = fileDiffs.get(`${changeset.id}:${fileID}`)
      if (!fileDiff?.macroChunks) continue
      for (const chunk of fileDiff.macroChunks) {
        const result = new Map<string, LineComments>()
        for (const line of chunk.content) {
          const oldSide: LineSideComments = {
            hasOpenIssues: false,
            hasClosedIssues: false,
            hasNotes: false,
            comments: [],
          }
          const newSide: LineSideComments = {
            hasOpenIssues: false,
            hasClosedIssues: false,
            hasNotes: false,
            comments: [],
          }
          if (line.type !== kInsertedLine) {
            const byLineOld = byLine.get(line.oldID) || []
            oldSide.hasOpenIssues = hasOpenIssues(byLineOld)
            oldSide.hasClosedIssues = hasClosedIssues(byLineOld)
            oldSide.hasNotes = hasNotes(byLineOld)
            oldSide.comments = byLinePrimary.get(line.oldID) || []
          }
          if (line.type !== kDeletedLine) {
            const byLineNew = byLine.get(line.newID) || []
            newSide.hasOpenIssues = hasOpenIssues(byLineNew)
            newSide.hasClosedIssues = hasClosedIssues(byLineNew)
            newSide.hasNotes = hasNotes(byLineNew)
            newSide.comments = byLinePrimary.get(line.newID) || []
          }
          result.set(line.id, { oldSide, newSide })
        }
        byChunk.push(result)
      }
    }
    const sortByFirstLine = (comments: Comment[]) => {
      comments.sort((a, b) => b.location!.firstLine - a.location!.firstLine)
    }
    for (const comments of byFile.values()) {
      sortByFirstLine(comments.all)
      for (const byLine of comments.byLine.values()) sortByFirstLine(byLine)
    }
    return castImmutable(result)
  },
)

/*
export const getSelectedComments = createSelector(
  [getActiveFile, getAnchorLineID, getFocusLineID, getCommentsForChangeset],
  (file, anchorID, focusID, commentsForChangeset) => {
    if (!file) {
      return {}
    }
    const fileID = parseInt(file.substring(3), 10)
    var side
    var first
    var last
    if (anchorID !== null && focusID !== null) {
      side = anchorID.substring(0, 3)
      const anchorLine = parseInt(anchorID.substring(3), 10)
      const focusLine = parseInt(focusID.substring(3), 10)
      first = Math.min(anchorLine, focusLine)
      last = Math.max(anchorLine, focusLine)
    } else {
      side = anchorID.substring(0, 3)
      const anchorLine = parseInt(anchorID.substring(3), 10)
      first = anchorLine
      last = anchorLine
    }

    const comments = commentsForChangeset.byFile[fileID][side + "Side"]
    const selectedComments = {}
    for (let lineNumber = first; lineNumber <= last; ++lineNumber) {
      const commentsOnLine = comments[lineNumber]
      if (commentsOnLine) {
        for (let comment of commentsOnLine) {
          selectedComments[comment.id] = comment
        }
      }
    }

    var commentObject = {}
    for (const commentID in selectedComments) {
      const comment = selectedComments[commentID]
      const key = side + comment.location.last_line
      if (key in commentObject) {
        commentObject[key].push(comment)
      } else {
        commentObject[key] = [comment]
      }
    }
    return commentObject
  }
)
*/
