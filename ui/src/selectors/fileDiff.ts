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

const getCommentLocations = (state: State) =>
  state.resource.extra.commentLocations
// const getActiveFile = (state: State) => state.ui.codeLines.anchorPartition
// const getAnchorLineID = (state: State) => state.ui.codeLines.anchorEntity
// const getFocusLineID = (state: State) => state.ui.codeLines.focusEntity

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
  props: FileIDProp & GetChangesetProps
) => {
  const changeset = getChangeset(state, props)
  if (!changeset) return null
  return state.resource.filechanges.get(`${changeset.id}:${props.fileID}`)
}

export const getFileDiff = (
  state: State,
  props: FileIDProp & GetChangesetProps
) => {
  const changeset = getChangeset(state, props)
  if (!changeset) return null
  return state.resource.filediffs.get(`${changeset.id}:${props.fileID}`)
}

type CommentsByLine = Map<string, Comment[]>

export type CommentsByFileValue = {
  byLine: CommentsByLine
  byLinePrimary: CommentsByLine
  all: Comment[]
}

export type CommentsByFile = Map<FileID, CommentsByFileValue>

export type CommentsForChangeset = {
  inCommitMessage: Comment[]
  byFile: CommentsByFile
}

const addComment = (
  byLine: CommentsByLine,
  location: Location,
  lineNumber: number,
  comment: Comment
) => {
  const lineID = `${location.side!.charAt(0)}${lineNumber}`
  if (!byLine.has(lineID)) byLine.set(lineID, [])
  byLine.get(lineID)!.push(comment)
}

export const getCommentsForChangeset = createSelector(
  getCommentLocations,
  getCommentsForReview,
  getChangeset,
  (commentLocations, commentsForReview, changeset) => {
    const inCommitMessage: Comment[] = []
    const byFile: CommentsByFile = new Map()
    const result = {
      inCommitMessage,
      byFile,
    }
    if (!changeset || !changeset.files) return castImmutable(result)
    var commitID = null
    if (changeset.contributingCommits.length === 1) {
      commitID = changeset.toCommit
    }
    for (const fileID of changeset.files) {
      byFile.set(fileID, {
        byLine: new Map(),
        byLinePrimary: new Map(),
        all: [],
      })
    }
    for (const comment of commentsForReview) {
      const translatedLocation = commentLocations.get(
        `${changeset.id}:${comment.id}`
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
      if (!byFile.has(fileID)) continue
      const { byLine, byLinePrimary, all } = byFile.get(fileID)!
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
        translatedComment
      )
    }
    const sortByFirstLine = (comments: Comment[]) => {
      comments.sort((a, b) => b.location!.firstLine - a.location!.firstLine)
    }
    for (const comments of byFile.values()) {
      sortByFirstLine(comments.all)
      for (const byLine of comments.byLine.values()) sortByFirstLine(byLine)
    }
    return castImmutable(result)
  }
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
