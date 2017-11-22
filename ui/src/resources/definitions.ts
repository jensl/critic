import { assertIsObject, assertNumber } from "../debug"
import { JSONData, ResourceData } from "../types"
import { RequestParams, FetchJSONParams } from "../utils/Fetch.types"

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
import { ExcludeFields, ResourceTypes, RequestOptions } from "./types"

interface ResourceMap {
  get(id: any, defaultValue: any): any
}

type CreateRequestFunc = (...params: any[]) => FetchJSONParams
type CompleteRequestFunc = (options: RequestOptions, data?: JSONData) => void
type LookupFunc = (resource: ResourceMap, value: ResourceData) => any

type ResourceDefinition = {
  defaultParams?: RequestParams
  defaultInclude?: (keyof ResourceTypes)[]
  defaultExcludeFields?: ExcludeFields
  recordType: any
  createRequest?: CreateRequestFunc
  completeRequest?: CompleteRequestFunc
  lookup?: LookupFunc
}
type ResourceDefinitions = { [resourceName: string]: ResourceDefinition }

const resourceDefinitions: ResourceDefinitions = {
  batches: {
    defaultInclude: ["reviews"],
    recordType: Batch,
  },

  branches: {
    defaultInclude: ["branches", "commits", "repositories"],
    recordType: Branch,
  },

  changesets: {
    recordType: Changeset,
  },

  comments: {
    defaultInclude: ["changesets", "commits", "files"],
    defaultExcludeFields: {
      changesets: ["contributing_commits", "files", "review_state"],
    },
    recordType: Comment,
  },

  commits: {
    recordType: Commit,
  },

  extensions: {
    defaultInclude: ["extensionversions", "extensioninstallations"],
    recordType: Extension,
  },

  extensioninstallations: {
    recordType: ExtensionInstallation,
  },

  extensionversions: {
    recordType: ExtensionVersion,
  },

  filechanges: {
    recordType: FileChange,
  },

  filecontents: {
    recordType: FileContent,
  },

  filediffs: {
    completeRequest: (options) => {
      assertIsObject(options.data)
      const {
        changeset,
        changesetID,
        reviewID,
        repositoryID,
      }: {
        changeset?: Changeset
        changesetID?: number
        reviewID?: number
        repositoryID?: number
      } = options.data
      const params = options.params || {}
      const include = options.include || []
      params.compact = "yes"
      if (changeset) {
        params.changeset = changeset.id
      } else {
        assertNumber(changesetID)
        params.changeset = changesetID!
        include.push("commits", "changesets", "filechanges", "files")
      }
      if (typeof reviewID === "number") params.review = reviewID
      if (typeof repositoryID === "number") params.repository = repositoryID
      options.params = params
      options.include = include
      options.expectedStatus = [200, 202]
    },
    recordType: FileDiff,
  },

  files: {
    recordType: File,
  },

  mergeanalyses: {
    completeRequest: (options) => {
      options.params = { ...options.params, compact: "yes" }
      options.expectedStatus = [200, 202]
    },
    defaultInclude: ["changesets", "commits", "filechanges", "files"],
    recordType: MergeAnalysis,
  },

  rebases: {
    recordType: Rebase,
  },

  replies: {
    recordType: Reply,
  },

  repositories: {
    defaultInclude: ["commits"],
    defaultParams: { statistics: "default", head: "all" },
    recordType: Repository,
  },

  repositoryfilters: {
    defaultInclude: ["repositories", "users"],
    recordType: RepositoryFilter,
  },

  reviews: {
    defaultInclude: [
      "batches",
      "branches",
      "changesets:limit=20" as keyof ResourceTypes,
      "comments",
      "commits",
      "files",
      "rebases",
      "replies",
      "repositories",
      "reviewablefilechanges:limit=100" as keyof ResourceTypes,
      "reviewfilters",
      "reviewtags",
      "users",
    ],
    defaultExcludeFields: {
      changesets: [
        "completion_level",
        "contributing_commits",
        "review_state.comments",
      ],
      comments: ["location"],
      //reviews: ["pings"],
    },
    recordType: Review,
  },

  reviewfilters: {
    recordType: ReviewFilter,
  },

  reviewablefilechanges: {
    recordType: ReviewableFileChange,
  },

  reviewtags: {
    recordType: ReviewTag,
  },

  sessions: {
    defaultInclude: ["users"],
    recordType: Session,
  },

  systemevents: {
    recordType: SystemEvent,
  },

  systemsettings: {
    recordType: SystemSetting,
  },

  trackedbranches: {
    recordType: TrackedBranch,
  },

  trees: {
    recordType: Tree,
  },
  tutorials: {
    recordType: Tutorial,
  },
  useremails: {
    recordType: UserEmail,
  },
  users: {
    recordType: User,
  },
  usersettings: {
    defaultParams: {
      scope: "ui",
    },
    recordType: UserSetting,
  },
  usersshkeys: {
    recordType: UserSSHKey,
  },
}

export default resourceDefinitions
