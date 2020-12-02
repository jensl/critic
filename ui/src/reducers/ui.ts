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

import { combineReducers } from "redux"
import Immutable from "immutable"

import { Breadcrumb } from "../actions"
import { extension } from "./uiExtension"
//import { createExpandable } from "./uiExpandable"
import { codeLines } from "./uiCodeLines"
import { comment } from "./uiComment"
//import { commitList } from "./uiCommitList"
import { connectedInputs } from "./uiConnectedInput"
import flags from "./uiFlags"
import values from "./uiValues"
import { counters } from "./uiCounters"
import mouse from "./uiMouse"
import { resourceSubscriptions } from "./uiResourceSubscriptions"
import { selectionScope } from "./uiSelectionScope"
import { createTextField } from "./uiTextField"
import webSocket from "./uiWebSocket"
import { registry } from "./uiRegistry"
import session from "./uiSession"
import itemLists from "./uiItemList"

import {
  START,
  ADD_LINKIFIER,
  REMOVE_LINKIFIER,
  SET_BREADCRUMBS,
  KeyboardShortcutHandlerFunc,
  KeyboardShortcutScopeType,
  PUSH_KEYBOARD_SHORTCUT_SCOPE,
  POP_KEYBOARD_SHORTCUT_SCOPE,
  SET_SINGLE_SPACE_WIDTH,
  UPDATE_REVIEW_CATEGORY,
  ReviewCategory,
  SET_RECENT_BRANCHES,
  Toast,
  ADD_TOAST,
  SET_TOAST_STATE,
  TOAST_REMOVED,
  Action,
  LOGIN_REQUEST,
  LOGIN_FAILURE,
  LOGIN_SUCCESS,
} from "../actions"
/* import { SET_DO_DIRECTLY } from "../actions/uiCommitList"
import {
  EXPAND_FILE,
  COLLAPSE_FILE,
  SET_EXPANDABLE_FILES,
  SET_EXPANDED_FILES,
  SET_CURRENT_FILE,
} from "../actions/uiFileDiff"
import {
  DISCARD_UNPUBLISHED_CHANGES_INCLUDE_ITEM,
  DISCARD_UNPUBLISHED_CHANGES_EXCLUDE_ITEM,
} from "../actions/uiBatch"
import {
  SET_REVIEW_ISSUES_MODE,
  DISPLAY_CREATE_REVIEW_DIALOG,
  DISMISS_CREATE_REVIEW_DIALOG,
} from "../actions/uiReview"*/
/*import { DATA_UPDATE } from "../actions/data"
import {
  LOGIN_REQUEST,
  LOGIN_SUCCESS,
  LOGIN_FAILURE,
  LOGOUT_SUCCESS,
} from "../actions/session" */
import Token from "../utils/Token"
import { RepositoryID, BranchID, ReviewID } from "../resources/types"

class KeyboardShortcutScope extends Immutable.Record<{
  name: string
  handler: KeyboardShortcutHandlerFunc
  scopeType: KeyboardShortcutScopeType
  token: Token
}>({
  name: "",
  handler: (_event: KeyboardEvent) => false,
  scopeType: "default",
  token: Token.invalid,
}) {}

class FileTreeView extends Immutable.Record<{
  expandedFolders: Immutable.Set<string>
  selectedFolders: Immutable.Set<string>
  selectedFileIDs: Immutable.Set<number>
  lockedFolders: Immutable.Set<string>
  lockedFileIDs: Immutable.Set<number>
}>({
  expandedFolders: Immutable.Set(),
  selectedFolders: Immutable.Set(),
  selectedFileIDs: Immutable.Set(),
  lockedFolders: Immutable.Set(),
  lockedFileIDs: Immutable.Set(),
}) {}

/*
const CreateReviewDialog = Immutable.Record({
  branch: null,
  repository: null,
  commitIDs: null,
})

const AssignChangesPopUp = Immutable.Record({
  reviewID: null,
  fileID: null,
})

const AssignChangesDialog = Immutable.Record({
  reviewID: null,
  mode: null,
}) */

class Linkifier extends Immutable.Record<{
  pattern: string
  regexp: RegExp
  generateURL: (match: string[]) => string
}>(
  {
    pattern: "",
    regexp: new RegExp(""),
    generateURL: (_match: string[]) => "",
  },
  "Linkifier",
) {}

export type ReviewCategories = Immutable.Map<
  ReviewCategory,
  Immutable.List<ReviewID>
>

class State extends Immutable.Record<{
  started: boolean
  keyboardShortcutScopes: Immutable.Stack<KeyboardShortcutScope>
  recentBranches: Immutable.Map<RepositoryID, Immutable.List<BranchID>>
  singleSpaceWidth: number
  linkifiers: Immutable.Map<Token, Linkifier>
  breadcrumbs: Immutable.List<Breadcrumb>
  toasts: Immutable.List<Toast>
  reviewCategories: ReviewCategories
  fileTreeView: FileTreeView
  signInPending: boolean
}>({
  started: false,
  keyboardShortcutScopes: Immutable.Stack<KeyboardShortcutScope>(),
  recentBranches: Immutable.Map<RepositoryID, Immutable.List<BranchID>>(),
  singleSpaceWidth: -1,
  linkifiers: Immutable.Map<Token, Linkifier>(),
  breadcrumbs: Immutable.List<Breadcrumb>(),
  toasts: Immutable.List<Toast>(),
  reviewCategories: Immutable.Map<ReviewCategory, Immutable.List<ReviewID>>(),
  fileTreeView: new FileTreeView(),
  signInPending: false,
}) {}

// const defaultState = {
//   started: false,
//   userInfoExpanded: false,
//   assignedReviewersExpanded: false,
//   visibleModal: "",
//   modalError: "",
//   selectedUsers: [],
//   addUsername: "",
//   replyText: {},
//   rebaseTypeSelected: null,
//   moveRebase: false,
//   rebaseSHA1: "",
//   commentCreation: "",
//   user: null,
//   review: null,
//   repository: null,
//   changeset: null,
//   commitListDoDirectly: false,
//   expandableFileIDs: null,
//   currentFileID: null,
//   currentFileIsExpanded: false,
//   keyboardShortcutScopes: Immutable.Stack([new KeyboardShortcutScope()]),
//   singleSpaceWidth: null,
//   // fileTreeView: new FileTreeView(),
//   discardBatchIncludedItems: Immutable.Set(),
//   suggestions: [],
//   userInputValue: Immutable.List(),
//   activeBranchKey: null,
//   activeRepositoryID: null,
//   createReviewDialog: null,
//   recentBranches: Immutable.Map(),
//   assignChangesPopUp: null,
//   assignChangesDialog: null,
//   reviewIssuesMode: "all",
//   reviewListCount: Immutable.Map(),
//   toasts: Immutable.List(),
//   reviewCategories: Immutable.Map<ReviewCategory, Immutable.List<number>>([
//     ["incoming", Immutable.List()],
//     ["outgoing", Immutable.List()],
//     ["other", Immutable.List()],
//     ["open", Immutable.List()],
//   ]),
//   linkifiers: Immutable.Map<Token, Linkifier>(),
//   signInPending: false,
//   breadcrumbs: Immutable.List(),
// }

const rest = (state = new State(), action: Action) => {
  switch (action.type) {
    case START:
      return state.set("started", true)

    /*     case DOCUMENT_CLICKED:
      return { ...state, assignChangesPopUp: null }

    case EXPAND_USER_INFO:
      return Object.assign({}, state, {
        userInfoExpanded: action.willExpand,
      })

    case TOGGLE_ASSIGNED_REVIEWERS:
      return Object.assign({}, state, {
        assignedReviewersExpanded: !state.assignedReviewersExpanded,
      })

    case SHOW_MODAL:
      return Object.assign({}, state, {
        visibleModal: action.modal,
        modalError: "",
      })

    case SHOW_ERROR_IN_MODAL:
      return Object.assign({}, state, { modalError: action.error })

    case SELECTED_USERS:
      return Object.assign({}, state, { selectedUsers: action.users })

    case UPDATE_ADD_USERNAME:
      return Object.assign({}, state, { addUsername: action.username })

    case RESET_ADD_USERNAME:
      return Object.assign({}, state, { addUsername: "" })

    case HANDLE_REPLY_TEXT_CHANGE:
      newState = Object.assign({}, state)
      newReplyText = Object.assign({}, state.replyText)
      newReplyText[action.commentID] = action.text
      newState.replyText = newReplyText
      return newState

    case CLEAR_REPLY_TEXT:
      newState = Object.assign({}, state)
      newReplyText = Object.assign({}, state.replyText)
      delete newReplyText[action.commentID]
      newState.replyText = newReplyText
      return newState

    case SELECT_REBASE_TYPE:
      return Object.assign({}, state, {
        rebaseTypeSelected: action.rebaseType,
      })

    case CLEAR_REBASE_TYPE:
      return Object.assign({}, state, { rebaseTypeSelected: null })

    case SHOW_MOVE_REBASE:
      return Object.assign({}, state, { moveRebase: true })

    case HIDE_MOVE_REBASE:
      return Object.assign({}, state, { moveRebase: false })

    case CHANGE_REBASE_SHA1:
      return Object.assign({}, state, { rebaseSHA1: action.sha1 })

    case ADDING_NOTE:
      return Object.assign({}, state, { commentCreation: "note" })

    case ADDING_ISSUE:
      return Object.assign({}, state, { commentCreation: "issue" })

    case RESET_COMMENT_CREATION:
      return Object.assign({}, state, { commentCreation: "" })

    case SET_REVIEW_CONTEXT:
      return Object.assign({}, state, { review: action.review })

    case SET_REPOSITORY_CONTEXT:
      return Object.assign({}, state, { repository: action.repository })

    case SET_CHANGESET_CONTEXT:
      return Object.assign({}, state, { changeset: action.changeset })

    case SET_DO_DIRECTLY:
      return Object.assign({}, state, {
        commitListDoDirectly: action.value,
      })

    case SET_EXPANDABLE_FILES:
      return Object.assign({}, state, {
        expandableFileIDs: action.fileIDs,
        currentFileID: action.fileIDs.get(0),
        currentFileIsExpanded: false,
      })

    case SET_EXPANDED_FILES:
      return Object.assign({}, state, {
        currentFileIsExpanded: action.fileIDs.has(state.currentFileID),
      })

    case SET_CURRENT_FILE:
      return Object.assign({}, state, {
        currentFileID: action.fileID,
      })

    case EXPAND_FILE:
      return Object.assign({}, state, {
        currentFileID: action.fileID,
        currentFileIsExpanded: true,
      })

    case COLLAPSE_FILE:
      newState = Object.assign({}, state, {
        filesTopInView: Object.assign({}, state.filesTopInView, {
          [action.fileID]: false,
        }),
        filesBottomInView: Object.assign({}, state.filesBottomInView, {
          [action.fileID]: false,
        }),
      })
      if (state.currentFileID === action.fileID) {
        Object.assign(newState, {
          currentFileIsExpanded: false,
        })
      }
      return newState */

    case PUSH_KEYBOARD_SHORTCUT_SCOPE:
      return state.set(
        "keyboardShortcutScopes",
        state.keyboardShortcutScopes.push(new KeyboardShortcutScope(action)),
      )

    case POP_KEYBOARD_SHORTCUT_SCOPE:
      return state.set(
        "keyboardShortcutScopes",
        state.keyboardShortcutScopes.filterNot(
          (scope) => scope.token === action.token,
        ),
      )

    case SET_SINGLE_SPACE_WIDTH:
      return state.set("singleSpaceWidth", action.width)

    /* case DATA_UPDATE:
      if (action.updates.has("sessions") && action.updates.has("users")) {
        const userID = action.updates.get("sessions").first().user
        if (userID !== null) {
          const user = action.updates
            .get("users")
            .filter(user => user.id === userID)
            .first()
          return {
            ...state,
            user,
          }
        }
      }
      return state

    case SHOW_CONFIRM_PROMPT:
      return Object.assign({}, state, {
        confirmPrompt: new ConfirmPrompt(
          Object.assign({}, action, {
            accept: new ConfirmPromptChoice(action.accept),
            reject: new ConfirmPromptChoice(action.reject),
          })
        ),
      })

    case CANCEL_CONFIRM_PROMPT:
      return Object.assign({}, state, {
        confirmPrompt: null,
      })

    case FILE_TREE_VIEW_RESET:
      return {
        ...state,
        fileTreeView: new FileTreeView({
          expandedFolders: Immutable.Set(action.expandedFolders || []),
          selectedFolders: Immutable.Set(action.selectedFolders || []),
          selectedFileIDs: Immutable.Set(action.selectedFileIDs || []),
          lockedFolders: Immutable.Set(action.lockedFolders || []),
          lockedFileIDs: Immutable.Set(action.lockedFileIDs || []),
        }),
      }

    case FILE_TREE_VIEW_EXPAND_FOLDER:
      return {
        ...state,
        fileTreeView: state.fileTreeView.set(
          "expandedFolders",
          state.fileTreeView.expandedFolders.add(action.path)
        ),
      }

    case FILE_TREE_VIEW_COLLAPSE_FOLDER:
      return {
        ...state,
        fileTreeView: state.fileTreeView.set(
          "expandedFolders",
          state.fileTreeView.expandedFolders.delete(action.path)
        ),
      }

    case FILE_TREE_VIEW_SELECT_FOLDER:
      return {
        ...state,
        fileTreeView: state.fileTreeView.set(
          "selectedFolders",
          state.fileTreeView.selectedFolders.add(action.path)
        ),
      }

    case FILE_TREE_VIEW_DESELECT_FOLDER:
      return {
        ...state,
        fileTreeView: state.fileTreeView.set(
          "selectedFolders",
          state.fileTreeView.selectedFolders.delete(action.path)
        ),
      }

    case FILE_TREE_VIEW_SELECT_FILE:
      return {
        ...state,
        fileTreeView: state.fileTreeView.set(
          "selectedFileIDs",
          state.fileTreeView.selectedFileIDs.add(action.fileID)
        ),
      }

    case FILE_TREE_VIEW_DESELECT_FILE:
      return {
        ...state,
        fileTreeView: state.fileTreeView.set(
          "selectedFileIDs",
          state.fileTreeView.selectedFileIDs.delete(action.fileID)
        ),
      }

    case DISCARD_UNPUBLISHED_CHANGES_INCLUDE_ITEM:
      return {
        ...state,
        discardBatchIncludedItems: state.discardBatchIncludedItems.add(
          action.item
        ),
      }

    case DISCARD_UNPUBLISHED_CHANGES_EXCLUDE_ITEM:
      return {
        ...state,
        discardBatchIncludedItems: state.discardBatchIncludedItems.delete(
          action.item
        ),
      }

    case SET_SUGGESTIONS:
      return {
        ...state,
        suggestions: action.suggestions,
      }

    case SET_USER_INPUT_VALUE:
      return {
        ...state,
        userInputValue: Immutable.List(action.value),
      }

    case LOGOUT_SUCCESS:
      return {
        ...state,
        user: null,
      }

    case SET_ACTIVE_BRANCH:
      return {
        ...state,
        activeBranchKey: action.branchKey,
      }

    case SET_ACTIVE_REPOSITORY:
      return {
        ...state,
        activeRepositoryID: action.repositoryID,
      }

    case DISPLAY_CREATE_REVIEW_DIALOG:
      return {
        ...state,
        createReviewDialog: new CreateReviewDialog(action),
      } */

    case SET_RECENT_BRANCHES:
      return state.setIn(
        ["recentBranches", action.repositoryID],
        Immutable.List<number>(action.branchIDs),
      )

    /* case SHOW_ASSIGN_CHANGES_POP_UP:
      return {
        ...state,
        assignChangesPopUp: new AssignChangesPopUp(action),
      }

    case HIDE_ASSIGN_CHANGES_POP_UP:
      return { ...state, assignChangesPopUp: null }

    case SHOW_ASSIGN_CHANGES_DIALOG:
      return {
        ...state,
        assignChangesDialog: new AssignChangesDialog(action),
      }

    case HIDE_ASSIGN_CHANGES_DIALOG:
      return { ...state, assignChangesDialog: null }

    case SET_REVIEW_ISSUES_MODE:
      return { ...state, reviewIssuesMode: action.mode }

    case SET_REVIEW_LIST_COUNT:
      return {
        ...state,
        reviewListCount: state.reviewListCount.set(
          action.category,
          action.count
        ),
      }*/

    case UPDATE_REVIEW_CATEGORY:
      return state.setIn(
        ["reviewCategories", action.category],
        action.reviewIDs,
      )

    case ADD_TOAST:
      return state.set("toasts", state.toasts.push(action.toast))

    case SET_TOAST_STATE:
      return state.set(
        "toasts",
        state.toasts.map((toast) =>
          toast.token === action.token ? toast.withState(action.state) : toast,
        ),
      )

    case TOAST_REMOVED:
      return state.set(
        "toasts",
        state.toasts.filterNot((toast) => toast.token === action.token),
      )

    case ADD_LINKIFIER:
      return state.set(
        "linkifiers",
        state.linkifiers.set(
          action.token,
          new Linkifier({
            pattern: action.pattern,
            regexp: new RegExp("^" + action.pattern),
            generateURL: action.generateURL,
          }),
        ),
      )

    case REMOVE_LINKIFIER:
      return state.set("linkifiers", state.linkifiers.delete(action.token))

    case LOGIN_REQUEST:
      return state.set("signInPending", true)

    case LOGIN_SUCCESS:
    case LOGIN_FAILURE:
      return state.set("signInPending", false)

    case SET_BREADCRUMBS:
      return state.set("breadcrumbs", Immutable.List(action.crumbs))

    default:
      return state
  }
}

const textField = combineReducers({
  commentText: createTextField("COMMENT_TEXT"),
  batchComment: createTextField("BATCH_COMMENT"),
})

const ui = combineReducers({
  codeLines,
  comment,
  //comments: createExpandable("COMMENT"),
  //commitList,
  connectedInputs,
  counters,
  extension,
  //files: createExpandable("FILE", { single: "fileID", multiple: "fileIDs" }),
  flags,
  values,
  //inView,
  mouse,
  resourceSubscriptions,
  rest,
  selectionScope,
  textField,
  webSocket,
  registry,
  session,
  itemLists,
})

export default ui
