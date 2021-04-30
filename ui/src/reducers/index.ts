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

import {
  InvalidItem,
  Action,
  COMMIT_REFS_UPDATE,
  BRANCH_COMMITS_UPDATE,
  USER_SETTINGS_LOADED,
  DATA_UPDATE,
} from "../actions"

import ui from "./ui"
import produce from "./immer"

import Changeset from "../resources/changeset"
import Commit from "../resources/commit"
import Branch from "../resources/branch"
import Review from "../resources/review"
import Batch from "../resources/batch"
import Comment, { Location } from "../resources/comment"
import Extension from "../resources/extension"
import ExtensionInstallation from "../resources/extensioninstallation"
import File from "../resources/file"
import FileChange from "../resources/filechange"
import FileContent from "../resources/filecontent"
import FileDiff from "../resources/filediff"
import MergeAnalysis from "../resources/mergeanalysis"
import Repository from "../resources/repository"
import ReviewTag from "../resources/reviewtag"
import Session from "../resources/session"
import TrackedBranch from "../resources/trackedbranch"
import Tree from "../resources/tree"
import User from "../resources/user"
import UserSetting from "../resources/usersetting"
import ExtensionVersion from "../resources/extensionversion"
import Rebase from "../resources/rebase"
import Reply from "../resources/reply"
import RepositoryFilter from "../resources/repositoryfilter"
import ReviewableFileChange from "../resources/reviewablefilechange"
import ReviewFilter from "../resources/reviewfilter"
import SystemEvent from "../resources/systemevent"
import SystemSetting from "../resources/systemsetting"
import Tutorial from "../resources/tutorial"
import UserEmail from "../resources/useremail"
import UserSSHKey from "../resources/usersshkey"
import { CommitID, RebaseID, BranchID, UserID } from "../resources/types"
import ExtensionCall from "../resources/extensioncall"
import Setting from "../resources/setting"

export const assignNewData = (array: any[]) => {
  return array.reduce((accumulator: any, currentValue: any) => {
    accumulator[currentValue.id] = currentValue
    return accumulator
  }, {})
}

const commitRefs = produce(
  (draft: Map<string, CommitID | InvalidItem>, action: Action) => {
    if (action.type === COMMIT_REFS_UPDATE)
      for (const [ref, value] of action.refs) draft.set(ref, value)
  },
  new Map(),
)

export type CommitRefs = ReturnType<typeof commitRefs>

const commentLocations = produce(
  (draft: Map<string, Location>, action: Action) => {
    if (action.type === "DATA_UPDATE" && action.updates.has("comments")) {
      console.log({ action })
      const add = (comment: Comment, location: Location | null) => {
        if (location && location.changeset)
          draft.set(`${location.changeset}:${comment.id}`, location)
      }
      for (const comment of action.updates.get("comments") as Comment[]) {
        add(comment, comment.location)
        add(comment, comment.translatedLocation)
      }
    }
  },
  new Map(),
)

export type CommentLocations = ReturnType<typeof commentLocations>

class PerBranch {
  all: CommitID[]
  afterRebase: Map<RebaseID, CommitID[]>

  constructor() {
    this.all = []
    this.afterRebase = new Map()
  }
}

const branchCommits = produce(
  (draft: Map<BranchID, PerBranch>, action: Action) => {
    if (action.type === BRANCH_COMMITS_UPDATE) {
      const { branchID, afterRebaseID, commitIDs } = action
      let perBranch = draft.get(branchID)
      if (!perBranch) draft.set(branchID, (perBranch = new PerBranch()))
      if (afterRebaseID !== null)
        perBranch.afterRebase.set(afterRebaseID, commitIDs)
      else perBranch.all = commitIDs
    }
  },
  new Map(),
)

type TreesExtra = {
  byCommitPath: Map<string, string>
}

const trees = produce<TreesExtra>(
  (draft, action) => {
    if (action.type === "TREES_UPDATE") {
      const { repositoryID, commitID, path, sha1 } = action
      draft.byCommitPath.set(
        `${repositoryID}:${commitID}:${path}`,
        `${repositoryID}:${sha1}`,
      )
    }
  },
  { byCommitPath: new Map() },
)

type UserSettingsExtra = {
  loadedFor: UserID | null
}

const userSettings = produce<UserSettingsExtra>(
  (draft, action) => {
    switch (action.type) {
      case USER_SETTINGS_LOADED:
        draft.loadedFor = action.userID
        break

      case DATA_UPDATE:
        if (
          (action.updates &&
            action.updates.has("sessions") &&
            action.updates.get("sessions")?.[0]?.user !== draft.loadedFor) ||
          (action.deleted && action.deleted.has("sessions"))
        )
          draft.loadedFor = null
        break
    }
  },
  { loadedFor: null },
)

export const extra = combineReducers({
  branchCommits,
  commentLocations,
  commitRefs,
  trees,
  userSettings,
})

export const resource = combineReducers({
  batches: Batch.reducer,
  branches: Branch.reducer,
  changesets: Changeset.reducer,
  comments: Comment.reducer,
  commits: Commit.reducer,
  extensions: Extension.reducer,
  extensioncalls: ExtensionCall.reducer,
  extensioninstallations: ExtensionInstallation.reducer,
  extensionversions: ExtensionVersion.reducer,
  files: File.reducer,
  filechanges: FileChange.reducer,
  filecontents: FileContent.reducer,
  filediffs: FileDiff.reducer,
  mergeanalyses: MergeAnalysis.reducer,
  rebases: Rebase.reducer,
  replies: Reply.reducer,
  repositories: Repository.reducer,
  repositoryfilters: RepositoryFilter.reducer,
  reviews: Review.reducer,
  reviewablefilechanges: ReviewableFileChange.reducer,
  reviewfilters: ReviewFilter.reducer,
  reviewtags: ReviewTag.reducer,
  sessions: Session.reducer,
  settings: Setting.reducer,
  systemevents: SystemEvent.reducer,
  systemsettings: SystemSetting.reducer,
  trackedbranches: TrackedBranch.reducer,
  trees: Tree.reducer,
  tutorials: Tutorial.reducer,
  users: User.reducer,
  useremails: UserEmail.reducer,
  usersettings: UserSetting.reducer,
  usersshkeys: UserSSHKey.reducer,

  extra,
})

/* for (const resourceName of Object.keys(resources)) {
  if (!(resourceName in resourceReducers)) {
    resourceReducers[resourceName] = createCollection(resourceName)
  }
} */

/*export const recordTypes = Object.keys(resourceReducers)
  .map(resourceName => resourceReducers[resourceName].recordType)
  .filter(recordType => recordType !== null)*/

export const download = produce<Map<string, string>>((draft, action) => {
  if (action.type === "DOWNLOAD") draft.set(action.key, action.contents)
}, new Map())

const rootReducer = combineReducers({
  resource,
  download,
  ui,
})

export default rootReducer