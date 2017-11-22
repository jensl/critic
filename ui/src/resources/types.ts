import { JSONData } from "../types"
import {
  FetchJSONParams,
  HandleError,
  HTTPMethod,
  RequestParams,
} from "../utils/Fetch.types"
import Batch from "./batch"
import Branch from "./branch"
import Changeset from "./changeset"
import Comment from "./comment"
import Commit from "./commit"
import Extension from "./extension"
import ExtensionInstallation from "./extensioninstallation"
import ExtensionVersion from "./extensionversion"
import File from "./file"
import FileChange from "./filechange"
import FileContent from "./filecontent"
import FileDiff from "./filediff"
import MergeAnalysis from "./mergeanalysis"
import Rebase from "./rebase"
import Reply from "./reply"
import Repository from "./repository"
import RepositoryFilter from "./repositoryfilter"
import Review from "./review"
import ReviewableFileChange from "./reviewablefilechange"
import ReviewFilter from "./reviewfilter"
import ReviewTag from "./reviewtag"
import Session from "./session"
import SystemEvent from "./systemevent"
import SystemSetting from "./systemsetting"
import TrackedBranch from "./trackedbranch"
import Tree from "./tree"
import Tutorial from "./tutorial"
import User from "./user"
import UserEmail from "./useremail"
import UserSetting from "./usersetting"
import UserSSHKey from "./usersshkey"

export type BatchID = number
export type BranchID = number
export type ChangesetID = number
export type CommentID = number
export type CommitID = number
export type ExtensionID = number
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

export type ResourceTypes = {
  batches: Batch
  branches: Branch
  changesets: Changeset
  comments: Comment
  commits: Commit
  extensions: Extension
  extensioninstallations: ExtensionInstallation
  extensionversions: ExtensionVersion
  filechanges: FileChange
  filecontents: FileContent
  filediffs: FileDiff
  files: File
  mergeanalyses: MergeAnalysis
  rebases: Rebase
  replies: Reply
  repositories: Repository
  repositoryfilters: RepositoryFilter
  reviews: Review
  reviewfilters: ReviewFilter
  reviewablefilechanges: ReviewableFileChange
  reviewtags: ReviewTag
  sessions: Session
  systemevents: SystemEvent
  systemsettings: SystemSetting
  trackedbranches: TrackedBranch
  trees: Tree
  tutorials: Tutorial
  useremails: UserEmail
  users: User
  usersettings: UserSetting
  usersshkeys: UserSSHKey
}

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
}
