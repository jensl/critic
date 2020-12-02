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
import { UserSettingID, UserID } from "./types"

type UserSettingProps = {
  id: UserSettingID
  user: UserID
  name: string
  value: unknown
}

class UserSetting {
  [immerable] = true

  constructor(
    readonly id: UserSettingID,
    readonly user: UserID,
    readonly name: string,
    readonly value: unknown,
  ) {}

  static new(props: UserSettingProps) {
    return new UserSetting(props.id, props.user, props.name, props.value)
  }

  static reducer = combineReducers({
    byID: primaryMap<UserSetting, UserSettingID>("usersettings"),
    byName: lookupMap<UserSetting, string, UserSettingID>(
      "usersettings",
      (setting) => setting.name,
    ),
  })

  get props(): UserSettingProps {
    return this
  }
}

export default UserSetting
