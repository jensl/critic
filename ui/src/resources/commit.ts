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

import { ResourceData } from "../types"
import { primaryMap, lookupMap, auxilliaryMap } from "../reducers/resource"
import { CommitID, BranchID } from "./types"

type CommitUserInfoData = {
  name: string
  email: string
  timestamp: number
}

type CommitUserInfoProps = CommitUserInfoData

export class CommitUserInfo {
  constructor(
    readonly name: string,
    readonly email: string,
    readonly timestamp: number
  ) {}

  static new(props: CommitUserInfoProps) {
    return new CommitUserInfo(props.name, props.email, props.timestamp)
  }
}

type CommitData = {
  id: CommitID
  sha1: string
  summary: string
  message: string
  author: CommitUserInfoData
  committer: CommitUserInfoData
  parents: CommitID[]
  tree: string
  description: CommitDescriptionData | null
}

interface CommitProps {
  id: CommitID
  sha1: string
  summary: string
  message: string
  author: CommitUserInfo
  committer: CommitUserInfo
  parents: readonly CommitID[]
  tree: string
  description: CommitDescription | null
}

class Commit {
  constructor(
    readonly id: CommitID,
    readonly sha1: string,
    readonly summary: string,
    readonly message: string,
    readonly author: CommitUserInfo,
    readonly committer: CommitUserInfo,
    readonly parents: readonly CommitID[],
    readonly tree: string,
    readonly description: CommitDescription | null
  ) {}

  static new(props: CommitProps) {
    return new Commit(
      props.id,
      props.sha1,
      props.summary,
      props.message,
      props.author,
      props.committer,
      props.parents,
      props.tree,
      props.description
    )
  }

  static prepare(value: CommitData): CommitProps {
    return {
      ...value,
      author: CommitUserInfo.new(value.author),
      committer: CommitUserInfo.new(value.committer),
      description: CommitDescription.make(value.description),
    }
  }

  static reducer = combineReducers({
    byID: primaryMap<Commit, CommitID>("commits"),
    bySHA1: lookupMap<Commit, string, CommitID>(
      "commits",
      (commit) => commit.sha1
    ),
    description: auxilliaryMap<Commit, CommitID, CommitDescription>(
      "commits",
      (commit) => [commit.id, commit.description]
    ),
  })

  get props(): CommitProps {
    return this
  }
}

type CommitDescriptionData = {
  branch: null | BranchID
  tag: null | string
}

type CommitDescriptionProps = CommitDescriptionData

export class CommitDescription {
  constructor(readonly branch: BranchID | null, readonly tag: string | null) {}

  static new(props: CommitDescriptionProps) {
    return new CommitDescription(props.branch, props.tag)
  }

  static make(value: ResourceData | null) {
    return value && CommitDescription.new(value as CommitDescriptionProps)
  }
}

export default Commit

export type Commits = ReturnType<typeof Commit.reducer>
