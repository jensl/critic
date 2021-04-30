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
import { immerable } from "immer"

import { Breadcrumb, PushKeyboardShortcutScopeAction } from "../actions"
//import { extension } from "./uiExtension.ts"
import { codeLines } from "./uiCodeLines"
import flags from "./uiFlags"
import values from "./uiValues"
import { counters } from "./uiCounters"
import mouse from "./uiMouse"
import { selectionScope } from "./uiSelectionScope"
import webSocket from "./uiWebSocket"
import { registry } from "./uiRegistry"
import session from "./uiSession"
import itemLists from "./uiItemList"
import paginations from "./uiPagination"

import {
  START,
  ADD_LINKIFIER,
  REMOVE_LINKIFIER,
  ENSURE_BREADCRUMBS,
  TRIM_BREADCRUMBS,
  SET_BREADCRUMB,
  KeyboardShortcutHandlerFunc,
  KeyboardShortcutScopeType,
  PUSH_KEYBOARD_SHORTCUT_SCOPE,
  POP_KEYBOARD_SHORTCUT_SCOPE,
  SET_SINGLE_SPACE_WIDTH,
  UPDATE_REVIEW_CATEGORY,
  ReviewCategory,
  SET_RECENT_BRANCHES,
  LOGIN_REQUEST,
  LOGIN_FAILURE,
  LOGIN_SUCCESS,
} from "../actions"
import Token from "../utils/Token"
import { RepositoryID, BranchID, ReviewID } from "../resources/types"
import produce from "./immer"

class KeyboardShortcutScope {
  [immerable] = true

  constructor(
    readonly name: string,
    readonly handler: KeyboardShortcutHandlerFunc,
    readonly scopeType: KeyboardShortcutScopeType,
    readonly token: Token,
  ) {}

  static new({
    name,
    handler,
    scopeType,
    token,
  }: PushKeyboardShortcutScopeAction) {
    return new KeyboardShortcutScope(name, handler, scopeType, token)
  }
}

class FileTreeView {
  [immerable] = true

  constructor(
    readonly expandedFolders: ReadonlySet<string>,
    readonly selectedFolders: ReadonlySet<string>,
    readonly selectedFileIDs: ReadonlySet<number>,
    readonly lockedFolders: ReadonlySet<string>,
    readonly lockedFileIDs: ReadonlySet<number>,
  ) {}

  static default() {
    return new FileTreeView(
      new Set(),
      new Set(),
      new Set(),
      new Set(),
      new Set(),
    )
  }
}

class Linkifier {
  [immerable] = true

  constructor(
    readonly pattern: string,
    readonly regexp: RegExp,
    readonly generateURL: (match: string[]) => string,
  ) {}
}

class State {
  [immerable] = true

  constructor(
    readonly started: boolean,
    readonly keyboardShortcutScopes: readonly KeyboardShortcutScope[],
    readonly recentBranches: ReadonlyMap<RepositoryID, readonly BranchID[]>,
    readonly singleSpaceWidth: number,
    readonly linkifiers: ReadonlyMap<Token, Linkifier>,
    readonly breadcrumbs: readonly Breadcrumb[],
    readonly reviewCategories: ReadonlyMap<ReviewCategory, readonly ReviewID[]>,
    readonly fileTreeView: FileTreeView,
    readonly signInPending: boolean,
  ) {}

  static default() {
    return new State(
      false,
      [],
      new Map(),
      0,
      new Map(),
      [],
      new Map(),
      FileTreeView.default(),
      false,
    )
  }
}

// >({
//   started: false,
//   keyboardShortcutScopes: Immutable.Stack<KeyboardShortcutScope>(),
//   recentBranches: Immutable.Map<RepositoryID, Immutable.List<BranchID>>(),
//   singleSpaceWidth: -1,
//   linkifiers: Immutable.Map<Token, Linkifier>(),
//   breadcrumbs: Immutable.List<Breadcrumb>(),
//   toasts: Immutable.List<Toast>(),
//   reviewCategories: Immutable.Map<ReviewCategory, Immutable.List<ReviewID>>(),
//   fileTreeView: FileTreeView.default(),
//   signInPending: false,
// }) {}

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

const rest = produce<State>((draft, action) => {
  switch (action.type) {
    case START:
      draft.started = true
      break

    case PUSH_KEYBOARD_SHORTCUT_SCOPE:
      draft.keyboardShortcutScopes.push(KeyboardShortcutScope.new(action))
      break

    case POP_KEYBOARD_SHORTCUT_SCOPE:
      draft.keyboardShortcutScopes = draft.keyboardShortcutScopes.filter(
        (scope) => scope.token !== action.token,
      )
      break

    case SET_SINGLE_SPACE_WIDTH:
      draft.singleSpaceWidth = action.width
      break

    case SET_RECENT_BRANCHES:
      draft.recentBranches.set(action.repositoryID, action.branchIDs)
      break

    case UPDATE_REVIEW_CATEGORY:
      draft.reviewCategories.set(action.category, action.reviewIDs)
      break

    case ADD_LINKIFIER:
      draft.linkifiers.set(
        action.token,
        new Linkifier(
          action.pattern,
          new RegExp("^" + action.pattern),
          action.generateURL,
        ),
      )
      break

    case REMOVE_LINKIFIER:
      draft.linkifiers.delete(action.token)
      break

    case LOGIN_REQUEST:
      draft.signInPending = true
      break

    case LOGIN_SUCCESS:
    case LOGIN_FAILURE:
      draft.signInPending = false
      break

    case TRIM_BREADCRUMBS:
      draft.breadcrumbs.length = action.length
      break

    case SET_BREADCRUMB:
      draft.breadcrumbs[action.index] = action.crumb
      break
  }
}, State.default())

const ui = combineReducers({
  codeLines,
  counters,
  flags,
  values,
  mouse,
  rest,
  selectionScope,
  webSocket,
  registry,
  session,
  itemLists,
  paginations,
})

export default ui
