/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
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

import React, { useEffect, FunctionComponent } from "react"

import CssBaseline from "@material-ui/core/CssBaseline"
import { ThemeProvider } from "@material-ui/core/styles"

import { loadExtensionInstallations } from "../actions/extension"
import { loadSession } from "../actions/session"
import { loadUsers } from "../actions/user"
import { loadUserSettings } from "../actions/usersetting"
import { connectWebSocket } from "../actions/uiWebSocket"
import {
  useSubscription,
  useSubscriptionIf,
  id,
  useUserSetting,
} from "../utils"
import { ProvideHashContext } from "../utils/Hash"
import { lightTheme, darkTheme } from "../theme"

import Structure from "./Application.Structure"
import SignIn from "./Dialog.SignIn"
import userSettings from "../userSettings"
import { useSelector, useDispatch } from "../store"
import Extensions from "../extensions"
import { useSessionInfo } from "../utils/SessionContext"

const WithSessionInfo: FunctionComponent = () => {
  const [themeName] = useUserSetting(userSettings.theme)
  const theme = selectTheme(themeName)

  useSubscription(loadExtensionInstallations)

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ProvideHashContext>
        <Structure />
        <SignIn />
        <Extensions />
      </ProvideHashContext>
    </ThemeProvider>
  )
}

const Application: FunctionComponent = () => {
  const dispatch = useDispatch()
  const { hasSessionInfo, signedInUser } = useSessionInfo()
  const started = useSelector((state) => state.ui.rest.started)
  useSubscriptionIf(signedInUser !== null, loadUserSettings, id(signedInUser))
  useSubscription(loadSession)
  useSubscription(loadUsers)
  useEffect(() => dispatch(connectWebSocket()), [dispatch])
  return started && hasSessionInfo ? <WithSessionInfo /> : null
}

const selectTheme = (name: string) => {
  switch (name) {
    case "light":
    default:
      return lightTheme
    case "dark":
      return darkTheme
  }
}

export default Application
