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

import { Action, USER_SETTINGS_LOADED } from "."
import { assertNotNull } from "../debug"
import {
  createResource,
  fetch,
  updateResource,
  withArgument,
  withContext,
  withParameters,
} from "../resources"
import Setting from "../resources/setting"
import { UserID } from "../resources/types"
import UserSetting from "../resources/usersetting"
import { AsyncThunk } from "../state"
import { JSONData } from "../types"
import { all } from "../utils/Functions"

const userSettingsLoaded = (userID: UserID): Action => ({
  type: USER_SETTINGS_LOADED,
  userID,
})

export const loadUserSettings = (userID: UserID): AsyncThunk<void> => async (
  dispatch,
) => {
  await dispatch(
    fetch(
      "settings",
      withContext("users", userID),
      withParameters({ scope: "ui" }),
    ),
  )
  //if (all(settings, (setting) => setting.user === userID))
  dispatch(userSettingsLoaded(userID))
}

export const defineUserSetting = (name: string, value: JSONData) =>
  createResource(
    "settings",
    { scope: "ui", name, value },
    withContext("users", "me"),
  )

export const updateUserSetting = (setting: Setting, value: JSONData) =>
  updateResource("settings", { value }, withArgument(setting.id))

export const setUserSetting = (
  setting: Setting | string,
  value: JSONData,
): AsyncThunk<Setting | null> => async (dispatch, getState) => {
  const {
    resource: { sessions, settings },
  } = getState()

  if (typeof sessions.get("current")?.user !== "number") return null

  if (typeof setting === "string") {
    const existingID = settings.byName.get(`ui::${setting}`)
    if (existingID) {
      const existing = settings.byID.get(existingID)
      assertNotNull(existing)
      return await dispatch(updateUserSetting(existing, value))
    }
    return await dispatch(defineUserSetting(setting, value))
  }

  return await dispatch(updateUserSetting(setting, value))
}
