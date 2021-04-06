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

import { createComment, setCommentText, deleteComment } from "./comment"
import { showToast } from "./uiToast"
import {
  CommentID,
  CommentType,
  ReviewID,
  ChangesetID,
  FileID,
  DiffSide,
} from "../resources/types"
import {
  EXPAND_COMMENT,
  Action,
  CommentInputProps,
  CLEAR_EXPANDED_COMMENTS,
  SET_HIGHLIGHTED_COMMENT,
  UPDATE_COMMENT_INPUT,
} from "."
import { Dispatch, GetState } from "../state"
import { CommentInput } from "../reducers/uiComment"

export const expandComment = (commentID: CommentID): Action => ({
  type: EXPAND_COMMENT,
  commentID,
})

export const COLLAPSE_COMMENT = "COLLAPSE_COMMENT"
export const collapseComment = (commentID: CommentID): Action => ({
  type: COLLAPSE_COMMENT,
  commentID,
})

export const clearExpandedComments = (): Action => ({
  type: CLEAR_EXPANDED_COMMENTS,
})

export const setHighlightedComment = (commentID: CommentID): Action => ({
  type: SET_HIGHLIGHTED_COMMENT,
  commentID,
})

export const updateCommentInput = (
  commentID: CommentID,
  updates: Partial<CommentInputProps>,
): Action => ({
  type: UPDATE_COMMENT_INPUT,
  commentID,
  updates,
})

export const createCodeComment = (
  type: CommentType,
  reviewID: ReviewID,
  changesetID: ChangesetID,
  fileID: FileID,
  side: DiffSide,
  firstLine: number,
  lastLine: number,
) => async (dispatch: Dispatch) => {
  dispatch({ type: "RESET_SELECTION_SCOPE" })

  const comment = await dispatch(
    createComment(reviewID, type, "", {
      changesetID,
      fileID,
      side,
      firstLine,
      lastLine,
    }),
  )

  if (comment) dispatch(expandComment(comment.id))

  return comment
}

export const raiseIssueInCode = (
  reviewID: ReviewID,
  changesetID: ChangesetID,
  fileID: FileID,
  side: DiffSide,
  firstLine: number,
  lastLine: number,
) =>
  createCodeComment(
    "issue",
    reviewID,
    changesetID,
    fileID,
    side,
    firstLine,
    lastLine,
  )

export const writeNoteInCode = (
  reviewID: ReviewID,
  changesetID: ChangesetID,
  fileID: FileID,
  side: DiffSide,
  firstLine: number,
  lastLine: number,
) =>
  createCodeComment(
    "note",
    reviewID,
    changesetID,
    fileID,
    side,
    firstLine,
    lastLine,
  )

export const saveCodeCommentInput = (
  commentInput: CommentInput,
  text: string,
  force = false,
) => async (dispatch: Dispatch, getState: GetState) => {
  const saveNow = async (commentInput: CommentInput) => {
    console.error("saveNow", { commentInput })
    if (commentInput.saveTimeoutID !== null) {
      clearTimeout(commentInput.saveTimeoutID)
    }
    const comment = await dispatch(setCommentText(commentInput.commentID, text))
    const updates: Partial<CommentInputProps> = { saveTimeoutID: null }
    if (comment) {
      updates.lastSaved = Date.now()
      updates.lastSaveFailed = false
      updates.lastSaveText = text
    } else {
      updates.lastSaveFailed = true
    }

    dispatch(updateCommentInput(commentInput.commentID, updates))
  }

  const { commentID } = commentInput

  const saveLater = () => {
    const inputs = getState().ui.comment.inputs
    if (inputs.has(commentID)) saveNow(inputs.get(commentID)!)
  }

  // Schedule a save three seconds from now. If we've already scheduled one,
  // postpone it.
  if (commentInput.saveTimeoutID !== null)
    clearTimeout(commentInput.saveTimeoutID)
  if (force) await saveNow(commentInput)
  else {
    const saveTimeoutID = window.setTimeout(saveLater, 1000)
    dispatch(updateCommentInput(commentID, { saveTimeoutID }))
  }
}

export const dismissCodeCommentInput = (
  commentInput: CommentInput,
  text: string,
) => async (dispatch: Dispatch) => {
  if (!text.trim()) {
    // Empty. Delete the draft comment.
    if (await dispatch(deleteComment(commentInput.commentID)))
      dispatch(showToast({ title: "Deleted empty comment", timeoutMS: 1000 }))
  } else if (commentInput.lastSaveText !== text) {
    dispatch(saveCodeCommentInput(commentInput, text, true))
  }
}
