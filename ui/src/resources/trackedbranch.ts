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
import { primaryMap, lookupMap } from "../reducers/resource"

type TrackedBranchData = {
  id: number
  is_disabled: boolean
  repository: number
  name: string
  branch: number | null
  source: SourceData
}

type TrackedBranchProps = {
  id: number
  is_disabled: boolean
  repository: number
  name: string
  branch: number | null
  source: Source
}

class TrackedBranch {
  constructor(
    readonly id: number,
    readonly isDisabled: boolean,
    readonly repository: number,
    readonly name: string,
    readonly branch: number | null,
    readonly source: Source
  ) {}

  static new(props: TrackedBranchProps) {
    return new TrackedBranch(
      props.id,
      props.is_disabled,
      props.repository,
      props.name,
      props.branch,
      props.source
    )
  }

  static prepare(value: TrackedBranchData): TrackedBranchProps {
    return {
      ...value,
      source: Source.new(value.source),
    }
  }

  static reducer = combineReducers({
    byID: primaryMap<TrackedBranch, number>("trackedbranches"),
    byName: lookupMap<TrackedBranch, string, number>(
      "trackedbranches",
      (branch) => `${branch.repository}:${branch.name}`
    ),
    byBranch: lookupMap<TrackedBranch, number, number>(
      "trackedbranches",
      (branch) => branch.branch
    ),
  })

  get props(): TrackedBranchProps {
    return { ...this, is_disabled: this.isDisabled }
  }
}

type SourceData = {
  url: string
  name: string
}

type SourceProps = SourceData

class Source {
  constructor(readonly url: string, readonly name: string) {}

  static new(props: SourceProps) {
    return new Source(props.url, props.name)
  }
}

export default TrackedBranch
