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

import Token from "../utils/Token"
import { Dispatch } from "../state"
import {
  CLEAR_FLAG,
  ClearFlagAction,
  SET_FLAG,
  SetFlagAction,
  TOGGLE_FLAG,
  ToggleFlagAction,
  UPDATE_COUNTER,
  UpdateCounterAction,
  GenerateURLFunc,
  AddLinkifierAction,
  ADD_LINKIFIER,
  REMOVE_LINKIFIER,
  RemoveLinkifierAction,
  KeyboardShortcutHandlerFunc,
  KeyboardShortcutScopeType,
  PUSH_KEYBOARD_SHORTCUT_SCOPE,
  PopKeyboardShortcutScopeAction,
  POP_KEYBOARD_SHORTCUT_SCOPE,
  SetSingleSpaceWidthAction,
  SET_SINGLE_SPACE_WIDTH,
} from "."

export const SHOW_SIGNIN_DIALOG_FLAG = "show-signin-dialog"

export const setFlag = (flag: string): SetFlagAction => ({
  type: SET_FLAG,
  flag,
})

export const clearFlag = (flag: string): ClearFlagAction => ({
  type: CLEAR_FLAG,
  flag,
})

export const toggleFlag = (flag: string): ToggleFlagAction => ({
  type: TOGGLE_FLAG,
  flag,
})

export const incrementCounter = (counter: string): UpdateCounterAction => ({
  type: UPDATE_COUNTER,
  counter,
  update: 1,
})
export const decrementCounter = (counter: string): UpdateCounterAction => ({
  type: UPDATE_COUNTER,
  counter,
  update: -1,
})

/*
export const EXPAND_USER_INFO = "EXPAND_USER_INFO"
export const expandUserInfo = willExpand => ({
  type: EXPAND_USER_INFO,
  willExpand: willExpand,
})

export const TOGGLE_ASSIGNED_REVIEWERS = "TOGGLE_ASSIGNED_REVIEWERS"
export const toggleAssignedReviewers = () => ({
  type: TOGGLE_ASSIGNED_REVIEWERS,
})

export const SHOW_MODAL = "SHOW_MODAL"
export const showModal = modal => ({
  type: SHOW_MODAL,
  modal,
})

export const SHOW_ERROR_IN_MODAL = "SHOW_ERROR_IN_MODAL"
export const showErrorInModal = error => ({
  type: SHOW_ERROR_IN_MODAL,
  error,
})

export const SELECTED_USERS = "SELECTED_USERS"
export const selectedUsers = users => ({
  type: SELECTED_USERS,
  users,
})

export const UPDATE_ADD_USERNAME = "UPDATE_ADD_USERNAME"
export const updateAddUsername = username => ({
  type: UPDATE_ADD_USERNAME,
  username,
})

export const RESET_ADD_USERNAME = "RESET_ADD_USERNAME"
export const resetAddUsername = () => ({
  type: RESET_ADD_USERNAME,
})

export const HANDLE_REPLY_TEXT_CHANGE = "HANDLE_REPLY_TEXT_CHANGE"
export const handleReplyTextChange = (commentID, text) => ({
  type: HANDLE_REPLY_TEXT_CHANGE,
  commentID,
  text,
})

export const CLEAR_REPLY_TEXT = "CLEAR_REPLY_TEXT"
export const clearReplyText = commentID => ({
  type: CLEAR_REPLY_TEXT,
  commentID,
})

export const HANDLE_COMMENT_TEXT_CHANGE = "HANDLE_COMMENT_TEXT_CHANGE"
export const handleCommentTextChange = content => ({
  type: HANDLE_COMMENT_TEXT_CHANGE,
  content,
})

export const CLEAR_COMMENT_TEXT = "CLEAR_COMMENT_TEXT"
export const clearCommentText = () => ({
  type: CLEAR_COMMENT_TEXT,
})

export const SELECT_REBASE_TYPE = "SELECT_REBASE_TYPE"
export const selectRebaseType = rebaseType => ({
  type: SELECT_REBASE_TYPE,
  rebaseType,
})

export const CLEAR_REBASE_TYPE = "CLEAR_REBASE_TYPE"
export const clearRebaseType = () => ({
  type: CLEAR_REBASE_TYPE,
})

export const SHOW_MOVE_REBASE = "SHOW_MOVE_REBASE"
export const showMoveRebase = () => ({
  type: SHOW_MOVE_REBASE,
})

export const HIDE_MOVE_REBASE = "HIDE_MOVE_REBASE"
export const hideMoveRebase = () => ({
  type: HIDE_MOVE_REBASE,
})

export const CHANGE_REBASE_SHA1 = "CHANGE_REBASE_SHA1"
export const changeRebaseSHA1 = sha1 => ({
  type: CHANGE_REBASE_SHA1,
  sha1,
})

export const ADDING_NOTE = "ADDING_NOTE"
export const addingNote = () => ({
  type: ADDING_NOTE,
})

export const ADDING_ISSUE = "ADDING_ISSUE"
export const addingIssue = () => ({
  type: ADDING_ISSUE,
})

export const RESET_COMMENT_CREATION = "RESET_COMMENT_CREATION"
export const resetCommentCreation = () => ({
  type: RESET_COMMENT_CREATION,
})

export const HANDLE_BATCH_COMMENT_CHANGE = "HANDLE_BATCH_COMMENT_CHANGE"
export const handleBatchCommentChange = content => ({
  type: HANDLE_BATCH_COMMENT_CHANGE,
  content,
})

export const RESET_BATCH_COMMENT = "RESET_BATCH_COMMENT"
export const resetBatchComment = () => ({
  type: RESET_BATCH_COMMENT,
})

export const SET_REVIEW_CONTEXT = "SET_REVIEW_CONTEXT"
export const setReviewContext = review => ({
  type: SET_REVIEW_CONTEXT,
  review,
})

export const SET_REPOSITORY_CONTEXT = "SET_REPOSITORY_CONTEXT"
export const setRepositoryContext = repository => ({
  type: SET_REPOSITORY_CONTEXT,
  repository,
})

export const SET_CHANGESET_CONTEXT = "SET_CHANGESET_CONTEXT"
export const setChangesetContext = changeset => ({
  type: SET_CHANGESET_CONTEXT,
  changeset,
})*/

export const pushKeyboardShortcutScope = (
  name: string,
  handler: KeyboardShortcutHandlerFunc,
  scopeType: KeyboardShortcutScopeType = "default",
) => (dispatch: Dispatch): Token => {
  const token = Token.create()
  dispatch({
    type: PUSH_KEYBOARD_SHORTCUT_SCOPE,
    name,
    handler,
    scopeType,
    token,
  })
  return token
}

export const popKeyboardShortcutScope = (
  token: Token,
): PopKeyboardShortcutScopeAction => ({
  type: POP_KEYBOARD_SHORTCUT_SCOPE,
  token,
})

export const setSingleSpaceWidth = (
  width: number,
): SetSingleSpaceWidthAction => ({
  type: SET_SINGLE_SPACE_WIDTH,
  width,
})

/*export const SHOW_CONFIRM_PROMPT = "SHOW_CONFIRM_PROMPT"
export const showConfirmPrompt = ({ title, details, accept, reject }) => ({
  type: SHOW_CONFIRM_PROMPT,
  title,
  details,
  accept,
  reject,
})

export const CANCEL_CONFIRM_PROMPT = "CANCEL_CONFIRM_PROMPT"
export const cancelConfirmPrompt = () => ({
  type: CANCEL_CONFIRM_PROMPT,
})

export const FILE_TREE_VIEW_RESET = "FILE_TREE_VIEW_RESET"
export const fileTreeViewReset = ({
  expandedFolders = null,
  selectedFolders = null,
  selectedFileIDs = null,
  lockedFolders = null,
  lockedFileIDs = null,
} = {}) => ({
  type: FILE_TREE_VIEW_RESET,
  expandedFolders,
  selectedFolders,
  selectedFileIDs,
  lockedFolders,
  lockedFileIDs,
})

export const FILE_TREE_VIEW_EXPAND_FOLDER = "FILE_TREE_VIEW_EXPAND_FOLDER"
export const fileTreeViewExpandFolder = path => ({
  type: FILE_TREE_VIEW_EXPAND_FOLDER,
  path,
})

export const FILE_TREE_VIEW_COLLAPSE_FOLDER = "FILE_TREE_VIEW_COLLAPSE_FOLDER"
export const fileTreeViewCollapseFolder = path => ({
  type: FILE_TREE_VIEW_COLLAPSE_FOLDER,
  path,
})

export const FILE_TREE_VIEW_SELECT_FOLDER = "FILE_TREE_VIEW_SELECT_FOLDER"
export const fileTreeViewSelectFolder = path => ({
  type: FILE_TREE_VIEW_SELECT_FOLDER,
  path,
})

export const FILE_TREE_VIEW_DESELECT_FOLDER = "FILE_TREE_VIEW_DESELECT_FOLDER"
export const fileTreeViewDeselectFolder = path => ({
  type: FILE_TREE_VIEW_DESELECT_FOLDER,
  path,
})

export const FILE_TREE_VIEW_SELECT_FILE = "FILE_TREE_VIEW_SELECT_FILE"
export const fileTreeViewSelectFile = fileID => ({
  type: FILE_TREE_VIEW_SELECT_FILE,
  fileID,
})

export const FILE_TREE_VIEW_DESELECT_FILE = "FILE_TREE_VIEW_DESELECT_FILE"
export const fileTreeViewDeselectFile = fileID => ({
  type: FILE_TREE_VIEW_DESELECT_FILE,
  fileID,
})

export const SET_SUGGESTIONS = "SET_SUGGESTIONS"
export const setSuggestions = (suggestions = []) => ({
  type: SET_SUGGESTIONS,
  suggestions,
})

export const SET_USER_INPUT_VALUE = "SET_USER_INPUT_VALUE"
export const setUserInputValue = value => ({
  type: SET_USER_INPUT_VALUE,
  value,
})

export const SET_ACTIVE_BRANCH = "SET_ACTIVE_BRANCH"
export const setActiveBranch = branchKey => ({
  type: SET_ACTIVE_BRANCH,
  branchKey,
})

export const SET_ACTIVE_REPOSITORY = "SET_ACTIVE_REPOSITORY"
export const setActiveRepository = repositoryID => ({
  type: SET_ACTIVE_REPOSITORY,
  repositoryID,
})

export const SHOW_ASSIGN_CHANGES_POP_UP = "SHOW_ASSIGN_CHANGES_POP_UP"
export const showAssignChangesPopUp = ({ reviewID, fileID }) => ({
  type: SHOW_ASSIGN_CHANGES_POP_UP,
  reviewID,
  fileID,
})

export const HIDE_ASSIGN_CHANGES_POP_UP = "HIDE_ASSIGN_CHANGES_POP_UP"
export const hideAssignChangesPopUp = () => ({
  type: HIDE_ASSIGN_CHANGES_POP_UP,
})

export const SHOW_ASSIGN_CHANGES_DIALOG = "SHOW_ASSIGN_CHANGES_DIALOG"
export const showAssignChangesDialog = ({ reviewID, mode }) => ({
  type: SHOW_ASSIGN_CHANGES_DIALOG,
  reviewID,
  mode,
})

export const HIDE_ASSIGN_CHANGES_DIALOG = "HIDE_ASSIGN_CHANGES_DIALOG"
export const hideAssignChangesDialog = () => ({
  type: HIDE_ASSIGN_CHANGES_DIALOG,
})

export const SET_REVIEW_LIST_COUNT = "SET_REVIEW_LIST_COUNT"
export const setReviewListCount = ({ category, count = 10 }) => ({
  type: SET_REVIEW_LIST_COUNT,
  category,
  count,
})*/

export const addLinkifier = (pattern: string, generateURL: GenerateURLFunc) => (
  dispatch: Dispatch,
) => {
  const token = Token.create()
  dispatch<AddLinkifierAction>({
    type: ADD_LINKIFIER,
    token,
    pattern,
    generateURL,
  })
  return token
}

export const removeLinkifier = (token: Token): RemoveLinkifierAction => ({
  type: REMOVE_LINKIFIER,
  token,
})
