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

import { primaryMap, lookupMap } from "../reducers/resource"
import { RepositoryID } from "./types"

type RepositoryData = {
  id: RepositoryID
  name: string
  path: string
  documentation_path: string | null
  urls: string[]
  statistics: StatisticsData
  head: HeadData
}

type RepositoryProps = {
  id: RepositoryID
  name: string
  path: string
  documentation_path: string | null
  urls: readonly string[]
  statistics: Statistics
  head: Head
}

class Repository {
  [immerable] = true

  constructor(
    readonly id: RepositoryID,
    readonly name: string,
    readonly path: string,
    readonly documentationPath: string | null,
    readonly urls: readonly string[],
    readonly statistics: Statistics,
    readonly head: Head,
  ) {}

  static new(props: RepositoryProps) {
    return new Repository(
      props.id,
      props.name,
      props.path,
      props.documentation_path,
      props.urls,
      props.statistics,
      props.head,
    )
  }

  static prepare(value: RepositoryData): RepositoryProps {
    return {
      ...value,
      statistics: value.statistics && Statistics.new(value.statistics),
      head: value.head && Head.new(value.head),
    }
  }

  static reducer = combineReducers({
    byID: primaryMap<Repository, number>("repositories"),
    byName: lookupMap<Repository, string, number>(
      "repositories",
      (repository) => repository.name,
    ),
  })

  get props(): RepositoryProps {
    return { ...this, documentation_path: this.documentationPath }
  }
}

type StatisticsData = {
  commits: number
  branches: number
  reviews: number
}

type StatisticsProps = StatisticsData

class Statistics {
  [immerable] = true

  constructor(
    readonly commits: number,
    readonly branches: number,
    readonly reviews: number,
  ) {}

  static new(props: StatisticsProps) {
    return new Statistics(props.commits, props.branches, props.reviews)
  }
}

type HeadData = {
  commit: null | number
  branch: null | number
  value: null | number
}

type HeadProps = HeadData

class Head {
  [immerable] = true

  constructor(
    readonly commit: null | number,
    readonly branch: null | number,
    readonly value: null | number,
  ) {}

  static new(props: HeadProps) {
    return new Head(props.commit, props.branch, props.value)
  }
}

export default Repository

export type Repositories = ReturnType<typeof Repository.reducer>
