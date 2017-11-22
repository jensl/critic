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

import Immutable from "immutable"

import {
  DATA_UPDATE,
  DOCUMENT_CLICKED,
  SET_SELECTED_ELEMENTS,
  EXPAND_COMMENT,
  COLLAPSE_COMMENT,
  SET_HIGHLIGHTED_COMMENT,
  UPDATE_COMMENT_INPUT,
  Action,
} from "../actions"
import { CommentID } from "../resources/types"
import Comment from "../resources/comment"

export class CommentInput extends Immutable.Record<{
  commentID: CommentID
  lastSaved: number | null
  lastSaveFailed: boolean
  lastSaveText: string | null
  saveTimeoutID: number | null
}>({
  commentID: -1,
  lastSaved: null,
  lastSaveFailed: false,
  lastSaveText: null,
  saveTimeoutID: null,
}) {}

class State extends Immutable.Record<{
  active: Immutable.Set<CommentInput>
  inputs: Immutable.Map<CommentID, CommentInput>
  showAtLine: any
  highlightedCommentID: CommentID | null
  expandedCommentIDs: Immutable.Set<CommentID>
}>({
  active: Immutable.Set(),
  inputs: Immutable.Map(),
  showAtLine: null,
  highlightedCommentID: null,
  expandedCommentIDs: Immutable.Set<CommentID>(),
}) {}

export const comment = (state = new State(), action: Action) => {
  switch (action.type) {
    case DOCUMENT_CLICKED:
      return state.merge({ showAtLine: null, highlightedCommentID: null })

    case EXPAND_COMMENT:
      return state.set(
        "expandedCommentIDs",
        state.expandedCommentIDs.add(action.commentID)
      )

    case COLLAPSE_COMMENT:
      return state.set(
        "expandedCommentIDs",
        state.expandedCommentIDs.delete(action.commentID)
      )

    case SET_SELECTED_ELEMENTS:
      if (!action.isPending)
        return state.merge({
          showAtLine: action.lastSelectedID,
          highlightedCommentID: null,
        })
      return state

    case SET_HIGHLIGHTED_COMMENT:
      return state.set("highlightedCommentID", action.commentID)

    case DATA_UPDATE:
      let nextInputs = state.inputs
      if (action.updates) {
        for (const comment of action.updates.get(
          "comments",
          Immutable.List<Comment>()
        ) as Immutable.List<Comment>) {
          if (
            !comment.is_draft &&
            !(comment.draft_changes && comment.draft_changes.reply)
          ) {
            nextInputs = nextInputs.delete(comment.id)
          } else if (!nextInputs.has(comment.id)) {
            nextInputs = nextInputs.set(
              comment.id,
              new CommentInput({ commentID: comment.id })
            )
          }
        }
      }
      if (action.deleted) {
        // Note: A deleted reply are handled by the previous block, as
        //       an updated comment going from having a draft reply to
        //       not having one.
        for (const commentID of action.deleted.get("comments", [])) {
          nextInputs = nextInputs.delete(commentID)
        }
      }
      return state.set("inputs", nextInputs)

    case UPDATE_COMMENT_INPUT:
      const { type, commentID, ...updates } = action
      if (state.inputs.has(commentID)) {
        return {
          ...state,
          inputs: state.inputs.mergeIn([commentID], updates),
        }
      }
      return state

    /*case UNPUBLISHED_CHANGES_PUBLISHED:
    case UNPUBLISHED_CHANGES_DISCARDED:
      return {
        ...state,
        active: state.active.filter(
          input => input.reviewID !== action.reviewID
        ),
      }*/

    default:
      return state
  }
}
