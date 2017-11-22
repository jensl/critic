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

import { primaryMap, lookupMap } from "../reducers/resource"
import { JSONData } from "../types"
import { SystemSettingID } from "./types"

type SystemSettingProps = {
  id: SystemSettingID
  key: string
  value: JSONData
}

class SystemSetting {
  constructor(
    readonly id: SystemSettingID,
    readonly key: string,
    readonly value: JSONData
  ) {}

  static new(props: SystemSettingProps) {
    return new SystemSetting(props.id, props.key, props.value)
  }

  static reducer = combineReducers({
    byID: primaryMap<SystemSetting, number>("systemsettings"),
    byKey: lookupMap<SystemSetting, string, number>(
      "repositories",
      (setting) => setting.key
    ),
  })

  get props(): SystemSettingProps {
    return this
  }
}

export default SystemSetting

export type SystemSettings = ReturnType<typeof SystemSetting.reducer>
