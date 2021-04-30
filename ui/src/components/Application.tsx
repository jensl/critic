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
import { ThemeProvider, makeStyles } from "@material-ui/core/styles"

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
import WebSocket from "../utils/WebSocketContext"
import { lightTheme, darkTheme } from "../theme"

import Structure from "./Application.Structure"
import SignIn from "./Dialog.SignIn"
import userSettings from "../userSettings"
import { useSelector, useDispatch } from "../store"
import Extensions from "../extensions"
import { useSessionInfo } from "../utils/SessionContext"
import { KeyboardEventHandler } from "../utils/KeyboardShortcuts"
import ResourceSubscriptions from "../utils/ResourceSubscriber"
import MouseTracker from "../utils/Mouse"

const selectTheme = (name: string) => {
  switch (name) {
    case "light":
    default:
      return lightTheme
    case "dark":
      return darkTheme
  }
}

const useStyles = makeStyles({
  resourceSubscriptions: { height: "100%" },
})

const WithSessionInfo: FunctionComponent = () => {
  const [themeName] = useUserSetting(userSettings.theme)
  const theme = selectTheme(themeName)

  useSubscription(loadExtensionInstallations, [])

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ProvideHashContext>
        <Structure />
        <SignIn global />
        <Extensions />
      </ProvideHashContext>
    </ThemeProvider>
  )
}

const WithoutSessionInfo: FunctionComponent = () => {
  const { hasSessionInfo, signedInUser } = useSessionInfo()
  const started = useSelector((state) => state.ui.rest.started)
  useSubscriptionIf(signedInUser !== null, loadUserSettings, [id(signedInUser)])
  useSubscription(loadSession, [])
  useSubscription(loadUsers, [])
  return started && hasSessionInfo ? <WithSessionInfo /> : null
}

const Application: FunctionComponent = () => {
  const classes = useStyles()
  const dispatch = useDispatch()
  //useEffect(() => dispatch(connectWebSocket()), [dispatch])
  return (
    <WebSocket>
      <MouseTracker>
        <KeyboardEventHandler>
          <ResourceSubscriptions className={classes.resourceSubscriptions}>
            <WithoutSessionInfo />
          </ResourceSubscriptions>
        </KeyboardEventHandler>
      </MouseTracker>
    </WebSocket>
  )
}

export default Application
