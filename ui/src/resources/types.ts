import { JSONData } from "../types"
import {
  FetchJSONParams,
  HandleError,
  HTTPMethod,
  RequestParams,
} from "../utils/Fetch.types"

export type AccessTokenID = number
export type BatchID = number
export type BranchID = number
export type ChangesetID = number
export type CommentID = number
export type CommitID = number
export type ExtensionID = number
export type ExtensionCallID = string
export type ExtensionInstallationID = number
export type ExtensionVersionID = number
export type FileID = number
export type FileChangeID = number
export type FileContentID = number
export type FileDiffID = number
export type MergeAnalysisID = number
export type RebaseID = number
export type ReplyID = number
export type RepositoryID = number
export type RepositoryFilterID = number
export type ReviewID = number
export type ReviewableFileChangeID = number
export type ReviewFilterID = number
export type ReviewTagID = number
export type SessionID = number
export type SettingID = number
export type SystemEventID = number
export type SystemSettingID = number
export type TrackedBranchID = number
export type TreeID = number
export type TutorialID = number
export type UserID = number
export type UserEmailID = number
export type UserSettingID = number
export type UserSSHKeyID = number

export type CommentType = "issue" | "note"
export type CommentLocationType = "commit-message" | "file-version"
export type IssueState = "open" | "resolved" | "addressed"
export type DiffSide = "old" | "new"

export type ExcludeFields = { [resourceName: string]: string[] }

export type RequestOptions = {
  context?: string
  args?: string[]
  params?: RequestParams
  include?: string[]
  handleError?: null | HandleError
  request?: FetchJSONParams
  payload?: JSONData
  method?: HTTPMethod
  expectedStatus?: number[]
  data?: any
  disableDefaults?: true
}
