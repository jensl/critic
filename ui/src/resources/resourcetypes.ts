import Batch from "./batch"
import Branch from "./branch"
import Changeset from "./changeset"
import Comment from "./comment"
import Commit from "./commit"
import Extension from "./extension"
import ExtensionCall from "./extensioncall"
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
import Setting from "./setting"
import SystemEvent from "./systemevent"
import SystemSetting from "./systemsetting"
import TrackedBranch from "./trackedbranch"
import Tree from "./tree"
import Tutorial from "./tutorial"
import User from "./user"
import UserEmail from "./useremail"
import UserSetting from "./usersetting"
import UserSSHKey from "./usersshkey"

export type ResourceTypes = {
  batches: Batch
  branches: Branch
  changesets: Changeset
  comments: Comment
  commits: Commit
  extensions: Extension
  extensioncalls: ExtensionCall
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
  settings: Setting
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
