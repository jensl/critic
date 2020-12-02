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

import { useCallback } from "react"

import Value from "./Value"
import { setUserSetting } from "../actions/usersetting"
import { Dispatch, State, GetState } from "../state"
import { useSelector, useDispatch } from "../store"
import { JSONData } from "../types"

export class NotLoaded extends Error {}

interface ConvertFromJSON<T> {
  (value: JSONData): T
}

interface ConvertToJSON<T> {
  (value: T): JSONData
}

type Convert<T> = {
  fromJSON: ConvertFromJSON<T>
  toJSON: ConvertToJSON<T>
}

export class UserSetting<T> {
  overrideValue: Value<T | undefined>

  constructor(
    readonly name: string,
    readonly fallbackValue: T,
    readonly convert: Convert<T> = {
      fromJSON: (value) => (value as unknown) as T,
      toJSON: (value) => (value as unknown) as JSONData,
    },
  ) {
    this.overrideValue = new Value<T | undefined>(
      `UserSetting/${name}`,
      undefined,
    )
  }

  read(state: State): T {
    const overrideValue = this.overrideValue.read(state)
    if (overrideValue !== undefined) return overrideValue
    const session = state.resource.sessions.get("current")
    if (!session || session.user === null) return this.fallbackValue
    const { byName, byID } = state.resource.usersettings
    if (state.resource.extra.userSettings.loadedFor !== session.user)
      return this.fallbackValue
    const userSetting = byID.get(byName.get(this.name) ?? -1)
    if (!userSetting) return this.fallbackValue
    return this.convert.fromJSON(userSetting.value as JSONData)
  }

  set(value: T) {
    console.error({ name: this.name, value })
    return async (dispatch: Dispatch, getState: GetState) => {
      dispatch(this.overrideValue.set(value))
      const session = getState().resource.sessions.get("current")
      if (session && session.user !== null) {
        await dispatch(setUserSetting(this.name, this.convert.toJSON(value)))
        dispatch(this.overrideValue.delete())
      }
    }
  }

  get setAction() {
    return (value: T) => this.set(value)
  }
}

export const useUserSetting = <T>(
  setting: UserSetting<T>,
): [T, (newValue: T) => Promise<void>] => {
  const dispatch = useDispatch()
  return [
    useSelector((state) => setting.read(state)),
    useCallback((newValue: T) => dispatch(setting.set(newValue)), [
      setting,
      dispatch,
    ]),
  ]
}

export default UserSetting
/*
const getUserSetting = (
  state,
  name,
  { defaultValue = null, onlyIfLoaded = false } = {}
) => {
  const defaultSetting = () =>
    new resources.usersettings.recordType({ name, value: defaultValue })
  const { user } = state.ui.rest
  if (!user) return defaultSetting()
  const { loadedForUserID, byName, byID } = state.resource.usersettings
  if (loadedForUserID === null)
    if (onlyIfLoaded) throw new NotLoaded()
    else return defaultSetting()
  const userSettingID = byName.get(name, null)
  if (userSettingID !== null) return byID.get(userSettingID)
  return defaultSetting()
}

export const requireUserSettings = compose(
  connect(state => {
    const {
      sessions,
      usersettings: { loadedForUserID },
    } = state.resource
    return {
      userSettingsLoaded:
        loadedForUserID === sessions.get("current", { user: null }).user,
    }
  }),
  stopIf(({ userSettingsLoaded }) => !userSettingsLoaded)
)

export default getUserSetting
*/
