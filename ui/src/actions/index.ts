import { FunctionComponent } from "react"
import { immerable } from "immer"

import {
  BranchID,
  RebaseID,
  CommitID,
  RepositoryID,
  ExtensionID,
  ExtensionInstallationID,
  ReviewID,
  UserID,
  CommentID,
  ChangesetID,
  FileID,
} from "../resources/types"
import { PublishedMessage } from "../protocol/WebSocket"
import Token from "../utils/Token"

export class InvalidItem {
  constructor(readonly id: number | string) {}
}

export const START = "START"
export interface StartAction {
  type: typeof START
}

export const LOGIN_REQUEST = "LOGIN_REQUEST"
export interface LoginRequestAction {
  type: typeof LOGIN_REQUEST
}

export const LOGIN_SUCCESS = "LOGIN_SUCCESS"
export interface LoginSuccessAction {
  type: typeof LOGIN_SUCCESS
}

export type LoginError = {
  title: string
  message: string
  code: string
}

export const LOGIN_FAILURE = "LOGIN_FAILURE"
export interface LoginFailureAction {
  type: typeof LOGIN_FAILURE
  error: LoginError
}

export const LOGOUT = "LOGOUT"
export interface LogoutAction {
  type: typeof LOGOUT
}

export const BRANCH_COMMITS_UPDATE = "BRANCH_COMMITS_UPDATE"
export interface BranchCommitsUpdateAction {
  type: typeof BRANCH_COMMITS_UPDATE
  branchID: BranchID
  afterRebaseID: RebaseID | null
  offset: number | null
  count: number | null
  commitIDs: CommitID[]
}

export const SET_CREATED_BRANCHES = "SET_CREATED_BRANCHES"
export interface SetCreatedBranchesAction {
  type: typeof SET_CREATED_BRANCHES
  branchIDs: BranchID[]
}

export const SET_UPDATED_BRANCHES = "SET_UPDATED_BRANCHES"
export interface SetUpdatedBranchesAction {
  type: typeof SET_UPDATED_BRANCHES
  branchIDs: BranchID[]
}

export const SET_RECENT_BRANCHES = "SET_RECENT_BRANCHES"
export interface SetRecentBranchesAction {
  type: typeof SET_RECENT_BRANCHES
  repositoryID: RepositoryID
  offset: number
  count: number
  branchIDs: BranchID[]
}

export const COMMIT_REFS_UPDATE = "COMMIT_REFS_UPDATE"
export interface CommitRefsUpdateAction {
  type: typeof COMMIT_REFS_UPDATE
  refs: Map<string, CommitID | InvalidItem>
}

export type BoundingRect = {
  top: number
  right: number
  bottom: number
  left: number
}

export type SelectionElementType = "commit" | "codeline"
export type SelectionElementID = string
export type SelectionScopeID = string

export const SET_SELECTION_SCOPE = "SET_SELECTION_SCOPE"
export interface SetSelectionScopeAction {
  type: typeof SET_SELECTION_SCOPE
  scopeID: SelectionScopeID
  elementType: SelectionElementType
  elements: { [id: string]: HTMLElement }
  elementIDs: SelectionElementID[]
  boundingRectsByID: { [id: string]: BoundingRect }
  boundingRect: BoundingRect
}

export const RESET_SELECTION_SCOPE = "RESET_SELECTION_SCOPE"
export interface ResetSelectionScopeAction {
  type: typeof RESET_SELECTION_SCOPE
  scopeID?: string
}

export const SET_SELECTION_RECT = "SET_SELECTION_RECT"
export interface SetSelectionRectAction {
  type: typeof SET_SELECTION_RECT
  boundingRect: BoundingRect
}

export const SET_SELECTED_ELEMENTS = "SET_SELECTED_ELEMENTS"
export interface SetSelectedElementsAction {
  type: typeof SET_SELECTED_ELEMENTS
  scopeID: SelectionScopeID
  selectedIDs: Set<SelectionElementID>
  firstSelectedID: SelectionElementID | null
  lastSelectedID: SelectionElementID | null
  isPending: boolean
  isRangeSelecting: boolean
}

export type SubscribedAction = (...args: any[]) => any

export const ADD_SUBSCRIPTION = "ADD_SUBSCRIPTION"
export interface AddSubscriptionAction {
  type: typeof ADD_SUBSCRIPTION
  action: SubscribedAction
  args: any[]
}

export const ADD_SUBSCRIBER = "ADD_SUBSCRIBER"
export interface AddSubscriberAction {
  type: typeof ADD_SUBSCRIBER
  action: SubscribedAction
  args: any[]
  token: Token
}

export const REMOVE_SUBSCRIBER = "REMOVE_SUBSCRIBER"
export interface RemoveSubscriberAction {
  type: typeof REMOVE_SUBSCRIBER
  action: SubscribedAction
  token: Token
}

export const CHECK_SUBSCRIPTION = "CHECK_SUBSCRIPTION"
export interface CheckSubscriptionAction {
  type: typeof CHECK_SUBSCRIPTION
  action: SubscribedAction
  args: any[]
}

export interface UIAddon {
  key: string
  extensionID: ExtensionID
  installationID: ExtensionInstallationID
  name: string
  implementation: any

  install: () => void
  uninstall: () => void
}

export const REGISTER_UI_ADDON = "REGISTER_UI_ADDON"
export interface RegisterUIAddonAction {
  type: typeof REGISTER_UI_ADDON
  uiAddon: UIAddon
}

export const UNREGISTER_UI_ADDON = "UNREGISTER_UI_ADDON"
export interface UnregisterUIAddonAction {
  type: typeof UNREGISTER_UI_ADDON
  uiAddon: UIAddon
}

export type RenderPageFunc = FunctionComponent<any>

export const ADD_EXTENSION_PAGE = "ADD_EXTENSION_PAGE"
export interface AddExtensionPageAction {
  type: typeof ADD_EXTENSION_PAGE
  uiAddon: UIAddon
  path: string
  render: RenderPageFunc
}

export type RenderLinkFunc = FunctionComponent<{ match: string[] }>

export const ADD_EXTENSION_LINKIFIER = "ADD_EXTENSION_LINKIFIER"
export interface AddExtensionLinkifierAction {
  type: typeof ADD_EXTENSION_LINKIFIER
  uiAddon: UIAddon
  pattern: string
  regexp: RegExp
  generateURL: GenerateURLFunc | null
  render: RenderLinkFunc | null
}

export const SET_FLAG = "SET_FLAG"
export interface SetFlagAction {
  type: typeof SET_FLAG
  flag: string
}
export const CLEAR_FLAG = "CLEAR_FLAG"
export interface ClearFlagAction {
  type: typeof CLEAR_FLAG
  flag: string
}
export const TOGGLE_FLAG = "TOGGLE_FLAG"
export interface ToggleFlagAction {
  type: typeof TOGGLE_FLAG
  flag: string
}

export const SET_VALUE = "SET_VALUE"
export interface SetValueAction {
  type: typeof SET_VALUE
  key: string
  value: any
}
export const DELETE_VALUE = "DELETE_VALUE"
export interface DeleteValueAction {
  type: typeof DELETE_VALUE
  key: string
}

export const UPDATE_COUNTER = "UPDATE_COUNTER"
export interface UpdateCounterAction {
  type: typeof UPDATE_COUNTER
  counter: string
  update: -1 | 1
}

export const DOCUMENT_CLICKED = "DOCUMENT_CLICKED"
export interface DocumentClickedAction {
  type: typeof DOCUMENT_CLICKED
}

export type GenerateURLFunc = (match: string[]) => string
export const ADD_LINKIFIER = "ADD_LINKIFIER"
export interface AddLinkifierAction {
  type: typeof ADD_LINKIFIER
  token: Token
  pattern: string
  generateURL: GenerateURLFunc
}

export const REMOVE_LINKIFIER = "REMOVE_LINKIFIER"
export interface RemoveLinkifierAction {
  type: typeof REMOVE_LINKIFIER
  token: Token
}

export const DATA_UPDATE = "DATA_UPDATE"
export type DataUpdateParams = {
  updates: Map<string, any[]>
  deleted: null | Map<string, Set<number | string>>
  invalid: null | Map<string, Set<number | string>>
}
export interface DataUpdateAction extends DataUpdateParams {
  type: typeof DATA_UPDATE
}

export type Breadcrumb = {
  category: string | null
  label: string
  path: string | null
}

export const ENSURE_BREADCRUMBS = "ENSURE_BREADCRUMBS"
export interface EnsureBreadcrumbsAction {
  type: typeof ENSURE_BREADCRUMBS
  length: number
}

export const TRIM_BREADCRUMBS = "TRIM_BREADCRUMBS"
export interface TrimBreadcrumbsAction {
  type: typeof TRIM_BREADCRUMBS
  length: number
}

export const SET_BREADCRUMB = "SET_BREADCRUMB"
export interface SetBreadcrumbAction {
  type: typeof SET_BREADCRUMB
  index: number
  crumb: Breadcrumb
}

export const PUSH_KEYBOARD_SHORTCUT_SCOPE = "PUSH_KEYBOARD_SHORTCUT_SCOPE"
export type KeyboardShortcutHandlerFunc = (
  ev: KeyboardEvent,
) => boolean | { preventDefault: boolean }
export type KeyboardShortcutScopeType =
  | "default"
  | "dialog"
  | "confirm"
  | "comment"
  | "tutorial"
export interface PushKeyboardShortcutScopeAction {
  type: typeof PUSH_KEYBOARD_SHORTCUT_SCOPE
  name: string
  handler: KeyboardShortcutHandlerFunc
  scopeType: KeyboardShortcutScopeType
  token: Token
}

export const POP_KEYBOARD_SHORTCUT_SCOPE = "POP_KEYBOARD_SHORTCUT_SCOPE"
export interface PopKeyboardShortcutScopeAction {
  type: typeof POP_KEYBOARD_SHORTCUT_SCOPE
  token: Token
}

export const SET_SINGLE_SPACE_WIDTH = "SET_SINGLE_SPACE_WIDTH"
export interface SetSingleSpaceWidthAction {
  type: typeof SET_SINGLE_SPACE_WIDTH
  width: number
}

export type ReviewCategory =
  | "incoming"
  | "outgoing"
  | "other"
  | "open"
  | "closed"

export const UPDATE_REVIEW_CATEGORY = "UPDATE_REVIEW_CATEGORY"
export interface UpdateReviewCategoryAction {
  type: typeof UPDATE_REVIEW_CATEGORY
  category: ReviewCategory
  reviewIDs: ReviewID[]
}

export const USER_SETTINGS_LOADED = "USER_SETTINGS_LOADED"
export interface UserSettingsLoadedAction {
  type: typeof USER_SETTINGS_LOADED
  userID: UserID
}

export type SaveActionCreator = (
  controlValue: string,
  wasDismissed: boolean,
) => any

export const UNPUBLISHED_CHANGES_PUBLISHED = "UNPUBLISHED_CHANGES_PUBLISHED"
export interface UnpublishedChangesPublishedAction {
  type: typeof UNPUBLISHED_CHANGES_PUBLISHED
  reviewID: ReviewID
}

export type DiscardItem =
  | "created_comments"
  | "written_replies"
  | "resolved_issues"
  | "reopened_issues"
  | "morphed_comments"
  | "reviewed_changes"
  | "unreviewed_changes"

export const UNPUBLISHED_CHANGES_DISCARDED = "UNPUBLISHED_CHANGES_DISCARDED"
export interface UnpublishedChangesDiscardedAction {
  type: typeof UNPUBLISHED_CHANGES_DISCARDED
  reviewID: ReviewID
  items: DiscardItem[]
}

export const EXPAND_COMMENT = "EXPAND_COMMENT"
export interface ExpandCommentAction {
  type: typeof EXPAND_COMMENT
  commentID: CommentID
}

export const COLLAPSE_COMMENT = "COLLAPSE_COMMENT"
export interface CollapseCommentAction {
  type: typeof COLLAPSE_COMMENT
  commentID: CommentID
}

export const CLEAR_EXPANDED_COMMENTS = "CLEAR_EXPANDED_COMMENTS"
export interface ClearExpandedCommentsAction {
  type: typeof CLEAR_EXPANDED_COMMENTS
}

export const SET_HIGHLIGHTED_COMMENT = "SET_HIGHLIGHTED_COMMENT"
export interface SetHighlightedCommentAction {
  type: typeof SET_HIGHLIGHTED_COMMENT
  commentID: CommentID
}

export type CommentInputProps = {
  lastSaved: number | null
  lastSaveFailed: boolean
  lastSaveText: string | null
  saveTimeoutID: number | null
}

export const UPDATE_COMMENT_INPUT = "UPDATE_COMMENT_INPUT"
export interface UpdateCommentInputAction {
  type: typeof UPDATE_COMMENT_INPUT
  commentID: CommentID
  updates: Partial<CommentInputProps>
}

export const SET_MOUSE_IS_DOWN = "SET_MOUSE_IS_DOWN"
export interface SetMouseIsDownAction {
  type: typeof SET_MOUSE_IS_DOWN
  value: boolean
}

export const SET_MOUSE_POSITION = "SET_MOUSE_POSITION"
export interface SetMousePositionAction {
  type: typeof SET_MOUSE_POSITION
  x: number
  y: number
}

export const WEB_SOCKET_CONNECTED = "WEB_SOCKET_CONNECTED"
export interface WebSocketConnectedAction {
  type: typeof WEB_SOCKET_CONNECTED
  connection: WebSocket
}

export const WEB_SOCKET_DISCONNECTED = "WEB_SOCKET_DISCONNECTED"
export interface WebSocketDisconnectedAction {
  type: typeof WEB_SOCKET_DISCONNECTED
}

export type ChannelCallback = (channel: string, message: any) => void

export const SUBSCRIBE_TO_CHANNEL = "SUBSCRIBE_TO_CHANNEL"
export interface SubscribeToChannelAction {
  type: typeof SUBSCRIBE_TO_CHANNEL
  channel: string
  callback: ChannelCallback
}

export const UNSUBSCRIBE_FROM_CHANNEL = "UNSUBSCRIBE_FROM_CHANNEL"
export interface UnsubscribeFromChannelAction {
  type: typeof UNSUBSCRIBE_FROM_CHANNEL
  channel: string
  callback: ChannelCallback
}

export type WebSocketListener = (payload: any) => "remove" | void

export const ADD_WEB_SOCKET_LISTENER = "ADD_WEB_SOCKET_LISTENER"
export interface AddWebSocketListenerAction {
  type: typeof ADD_WEB_SOCKET_LISTENER
  listener: WebSocketListener
}

export const REMOVE_WEB_SOCKET_LISTENER = "REMOVE_WEB_SOCKET_LISTENER"
export interface RemoveWebSocketListenerAction {
  type: typeof REMOVE_WEB_SOCKET_LISTENER
  listener: WebSocketListener
}

export const WEB_SOCKET_MESSAGE = "WEB_SOCKET_MESSAGE"
export interface WebSocketMessageAction {
  type: typeof WEB_SOCKET_MESSAGE
  channel: string
  message: PublishedMessage
}

export type AutomaticMode = "everything" | "relevant" | "reviewable" | "pending"

export class AutomaticChangesetEmpty extends Error {}
export class AutomaticChangesetImpossible extends Error {}

export const SET_AUTOMATIC_CHANGESET = "SET_AUTOMATIC_CHANGESET"
export interface SetAutomaticChangesetAction {
  type: typeof SET_AUTOMATIC_CHANGESET
  reviewID: ReviewID
  automatic: AutomaticMode
  changesetID:
    | ChangesetID
    | AutomaticChangesetEmpty
    | AutomaticChangesetImpossible
}

export type ToastState = "showing" | "hiding" | "removing"

type ToastProps = {
  token: null | Token
  type: null | string
  title: null | string
  content?: null | string | JSX.Element
  timeoutMS: null | number
  state?: null | ToastState
}

export class Toast {
  [immerable] = true

  constructor(
    readonly token: null | Token,
    readonly type: null | string,
    readonly title: null | string,
    readonly timeoutMS: null | number,
    readonly content?: null | string | JSX.Element,
    readonly state?: null | ToastState,
  ) {}

  static new(props: ToastProps) {
    return new Toast(
      props.token,
      props.type,
      props.title,
      props.timeoutMS,
      props.content,
      props.state,
    )
  }

  withState(state: ToastState) {
    return Toast.new({ ...this, state })
  }
}

export const ADD_TOAST = "ADD_TOAST"
export interface AddToastAction {
  type: typeof ADD_TOAST
  toast: Toast
}

export const SET_TOAST_STATE = "SET_TOAST_STATE"
export interface SetToastStateAction {
  type: typeof SET_TOAST_STATE
  token: Token
  state: ToastState
}

export const TOAST_REMOVED = "TOAST_REMOVED"
export interface ToastRemovedAction {
  type: typeof TOAST_REMOVED
  token: Token
}

export interface DownloadAction {
  type: "DOWNLOAD"
  key: string
  contents: string
}

export interface TreesUpdate {
  type: "TREES_UPDATE"
  repositoryID: RepositoryID
  commitID: CommitID
  path: string
  sha1: string
}

export type ItemList = "account-settings-panels" | "system-settings-panels"

export interface AddItemToList {
  type: "ADD_ITEM_TO_LIST"
  list: ItemList
  extensionID: ExtensionID
  itemID: string
  render: FunctionComponent<{}>
  before: string | null
  after: string | null
}

export interface ResetExtension {
  type: "RESET_EXTENSION"
  extensionID: ExtensionID
}

export interface FileDiffsUpdate {
  type: "FILEDIFFS_UPDATE"
  changesetID: ChangesetID
  fileID: FileID
  chunkIndex: number
  operation: "append" | "prepend"
  lines: readonly any[]
}

export const UPDATE_PAGINATION_ACTION = "UPDATE_PAGINATION_ACTION"
export type UpdatePaginationAction = {
  type: typeof UPDATE_PAGINATION_ACTION

  scope: string
  offset: number
  total: number
  itemIDs: readonly number[]
}

export type Action =
  | StartAction
  | CommitRefsUpdateAction
  | DataUpdateAction
  | BranchCommitsUpdateAction
  | SetCreatedBranchesAction
  | SetUpdatedBranchesAction
  | SetRecentBranchesAction
  | SetSelectionRectAction
  | SetSelectionScopeAction
  | ResetSelectionScopeAction
  | SetSelectedElementsAction
  | AddSubscriptionAction
  | AddSubscriberAction
  | RemoveSubscriberAction
  | CheckSubscriptionAction
  | SetFlagAction
  | ClearFlagAction
  | ToggleFlagAction
  | SetValueAction
  | DeleteValueAction
  | UpdateCounterAction
  | DocumentClickedAction
  | AddLinkifierAction
  | RemoveLinkifierAction
  | EnsureBreadcrumbsAction
  | TrimBreadcrumbsAction
  | SetBreadcrumbAction
  | PushKeyboardShortcutScopeAction
  | PopKeyboardShortcutScopeAction
  | SetSingleSpaceWidthAction
  | UpdateReviewCategoryAction
  | RegisterUIAddonAction
  | UnregisterUIAddonAction
  | AddExtensionPageAction
  | AddExtensionLinkifierAction
  | UserSettingsLoadedAction
  | ExpandCommentAction
  | CollapseCommentAction
  | ClearExpandedCommentsAction
  | SetHighlightedCommentAction
  | UpdateCommentInputAction
  | SetMouseIsDownAction
  | SetMousePositionAction
  | WebSocketConnectedAction
  | WebSocketDisconnectedAction
  | SubscribeToChannelAction
  | UnsubscribeFromChannelAction
  | AddWebSocketListenerAction
  | RemoveWebSocketListenerAction
  | SetAutomaticChangesetAction
  | AddToastAction
  | SetToastStateAction
  | ToastRemovedAction
  | LoginRequestAction
  | LoginSuccessAction
  | LoginFailureAction
  | LogoutAction
  | DownloadAction
  | TreesUpdate
  | AddItemToList
  | ResetExtension
  | FileDiffsUpdate
  | UpdatePaginationAction
  | WebSocketMessageAction
