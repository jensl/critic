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

import {
  createResource,
  fetch,
  updateResource,
  updateResources,
  withArgument,
  withParameters,
} from "../resources"
import SystemSetting from "../resources/systemsetting"
import { SystemSettingID } from "../resources/types"
import { JSONData } from "../types"
import { map } from "../utils"

export const loadSystemSettings = () => fetch("systemsettings")

export const loadSystemSetting = (systemSettingID: SystemSettingID) =>
  fetch("systemsettings", withArgument(systemSettingID))

export const loadSystemSettingByKey = (key: string) =>
  fetch("systemsettings", withParameters({ key }))

export const loadSystemSettingByPrefix = (prefix: string) =>
  fetch("systemsettings", withParameters({ prefix }))

export const setSystemSetting = (setting: SystemSetting, value: JSONData) =>
  updateResource("systemsettings", { value }, withArgument(setting.id))

export const setSystemSettings = (
  systemSettings: Map<SystemSettingID, JSONData>,
) =>
  updateResources(
    "systemsettings",
    map(systemSettings.entries(), ([id, value]) => ({ id, value })),
  )

export const addSystemEvent = (
  category: string,
  key: string,
  title: string,
  data: any = null,
) => createResource("systemevents", { category, key, title, data })
