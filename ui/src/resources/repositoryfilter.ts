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

import { immerable } from "immer"

import { primaryMap } from "../reducers/resource"
import { UserID } from "./types"

type RepositoryFilterData = {
  id: number
  subject: number
  repository: number
  type: "reviewer" | "watcher" | "ignored"
  path: string
  delegates: UserID[]
}

type RepositoryFilterProps = {
  id: number
  subject: number
  repository: number
  type: "reviewer" | "watcher" | "ignored"
  path: string
  delegates: Set<UserID>
}

class RepositoryFilter {
  [immerable] = true

  constructor(
    readonly id: number,
    readonly subject: number,
    readonly repository: number,
    readonly type: "reviewer" | "watcher" | "ignored",
    readonly path: string,
    readonly delegates: Set<UserID>,
  ) {}

  static new(props: RepositoryFilterProps) {
    return new RepositoryFilter(
      props.id,
      props.subject,
      props.repository,
      props.type,
      props.path,
      props.delegates,
    )
  }

  static prepare(value: RepositoryFilterData): RepositoryFilterProps {
    return {
      ...value,
      delegates: new Set(value.delegates),
    }
  }

  static reducer = primaryMap<RepositoryFilter, number>("repositoryfilters")

  get props(): RepositoryFilterProps {
    return this
  }
}

export default RepositoryFilter
