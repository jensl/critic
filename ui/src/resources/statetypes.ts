import { Batch as BatchResource } from "./batch"
import BranchResource from "./branch"
import ChangesetResource from "./changeset"
import CommentResource from "./comment"
import CommitResource from "./commit"
import ExtensionResource from "./extension"
import ExtensionCallResource from "./extensioncall"
import ExtensionInstallationResource from "./extensioninstallation"
import ExtensionVersionResource from "./extensionversion"
import FileResource from "./file"
import FileChangeResource from "./filechange"
import FileContentResource from "./filecontent"
import FileDiffResource from "./filediff"
import MergeAnalysisResource from "./mergeanalysis"
import RebaseResource from "./rebase"
import ReplyResource from "./reply"
import RepositoryResource from "./repository"
import RepositoryFilterResource from "./repositoryfilter"
import ReviewResource from "./review"
import ReviewableFileChangeResource from "./reviewablefilechange"
import ReviewFilterResource from "./reviewfilter"
import ReviewTagResource from "./reviewtag"
import SessionResource from "./session"
import SystemEventResource from "./systemevent"
import SystemSettingResource from "./systemsetting"
import TrackedBranchResource from "./trackedbranch"
import TreeResource from "./tree"
import TutorialResource from "./tutorial"
import UserResource from "./user"
import UserEmailResource from "./useremail"
import UserSettingResource from "./usersetting"
import UserSSHKeyResource from "./usersshkey"

export type Batch = ReturnType<typeof BatchResource.reducer>
export type Branch = ReturnType<typeof BranchResource.reducer>
export type Changeset = ReturnType<typeof ChangesetResource.reducer>
export type Comment = ReturnType<typeof CommentResource.reducer>
export type Commit = ReturnType<typeof CommitResource.reducer>
export type Extension = ReturnType<typeof ExtensionResource.reducer>
export type ExtensionCall = ReturnType<typeof ExtensionCallResource.reducer>
export type ExtensionInstallation = ReturnType<
  typeof ExtensionInstallationResource.reducer
>
export type ExtensionVersion = ReturnType<
  typeof ExtensionVersionResource.reducer
>
export type File = ReturnType<typeof FileResource.reducer>
export type FileChange = ReturnType<typeof FileChangeResource.reducer>
export type FileContent = ReturnType<typeof FileContentResource.reducer>
export type FileDiff = ReturnType<typeof FileDiffResource.reducer>
export type MergeAnalysis = ReturnType<typeof MergeAnalysisResource.reducer>
export type Rebase = ReturnType<typeof RebaseResource.reducer>
export type Reply = ReturnType<typeof ReplyResource.reducer>
export type Repository = ReturnType<typeof RepositoryResource.reducer>
export type RepositoryFilter = ReturnType<
  typeof RepositoryFilterResource.reducer
>
export type Review = ReturnType<typeof ReviewResource.reducer>
export type ReviewableFileChange = ReturnType<
  typeof ReviewableFileChangeResource.reducer
>
export type ReviewFilter = ReturnType<typeof ReviewFilterResource.reducer>
export type ReviewTag = ReturnType<typeof ReviewTagResource.reducer>
export type Session = ReturnType<typeof SessionResource.reducer>
export type SystemEvent = ReturnType<typeof SystemEventResource.reducer>
export type SystemSetting = ReturnType<typeof SystemSettingResource.reducer>
export type TrackedBranch = ReturnType<typeof TrackedBranchResource.reducer>
export type Tree = ReturnType<typeof TreeResource.reducer>
export type Tutorial = ReturnType<typeof TutorialResource.reducer>
export type User = ReturnType<typeof UserResource.reducer>
export type UserEmail = ReturnType<typeof UserEmailResource.reducer>
export type UserSetting = ReturnType<typeof UserSettingResource.reducer>
export type UserSSHKey = ReturnType<typeof UserSSHKeyResource.reducer>
