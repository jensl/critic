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
} from "../resources"
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
  const { primary: settings } = await dispatch(fetch("usersettings"))
  if (all(settings, (setting) => setting.user === userID))
    dispatch(userSettingsLoaded(userID))
}

export const defineUserSetting = (name: string, value: JSONData) =>
  createResource("usersettings", { scope: "ui", name, value })

export const updateUserSetting = (userSetting: UserSetting, value: JSONData) =>
  updateResource("usersettings", { value }, withArgument(userSetting.id))

export const setUserSetting = (
  userSetting: UserSetting | string,
  value: JSONData,
): AsyncThunk<UserSetting | null> => async (dispatch, getState) => {
  const {
    resource: { sessions, usersettings },
  } = getState()

  if (typeof sessions.get("current")?.user !== "number") return null

  if (typeof userSetting === "string") {
    const existingID = usersettings.byName.get(userSetting)
    if (existingID) {
      const existing = usersettings.byID.get(existingID)
      assertNotNull(existing)
      return await dispatch(updateUserSetting(existing, value))
    }
  } else {
    return await dispatch(updateUserSetting(userSetting, value))
  }

  return await dispatch(defineUserSetting(userSetting, value))
}
