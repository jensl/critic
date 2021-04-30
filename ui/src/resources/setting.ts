/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the
); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an
 BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import { combineReducers } from "redux"
import { immerable } from "immer"

import { primaryMap, lookupMap } from "../reducers/resource"
import {
  BranchID,
  ExtensionID,
  RepositoryID,
  ReviewID,
  SettingID,
  UserID,
} from "./types"

type SettingProps = {
  id: SettingID
  scope: string
  name: string
  value: unknown
  value_bytes_url: string | null
  user: UserID
  repository: RepositoryID
  branch: BranchID
  review: ReviewID
  extension: ExtensionID
}

class Setting {
  [immerable] = true

  constructor(
    readonly id: SettingID,
    readonly scope: string,
    readonly name: string,
    readonly value: unknown,
    readonly value_bytes_url: string | null,
    readonly user: UserID,
    readonly repository: RepositoryID,
    readonly branch: BranchID,
    readonly review: ReviewID,
    readonly extension: ExtensionID,
  ) {}

  static new(props: SettingProps) {
    return new Setting(
      props.id,
      props.scope,
      props.name,
      props.value,
      props.value_bytes_url,
      props.user,
      props.repository,
      props.branch,
      props.review,
      props.extension,
    )
  }

  static reducer = combineReducers({
    byID: primaryMap<Setting, SettingID>("settings"),
    byName: lookupMap<Setting, string, SettingID>(
      "settings",
      (setting) => `${setting.scope}::${setting.name}`,
    ),
  })

  get props(): SettingProps {
    return this
  }
}

export default Setting
