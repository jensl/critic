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

import React, { useContext, FunctionComponent } from "react"

import User from "../resources/user"
import { useResource } from "."

export type SessionID = number

const kNotSignedIn = -1

class Value {
  constructor(
    readonly hasSessionInfo: boolean = false,
    readonly sessionID: SessionID = kNotSignedIn,
    readonly isSignedIn: boolean = false,
    readonly signedInUser: User | null = null,
  ) {}
}

const SessionContext = React.createContext(new Value())

const SetSession: FunctionComponent = ({ children }) => {
  const session = useResource("sessions", (sessions) => sessions.get("current"))
  const sessionID = session?.user ?? kNotSignedIn
  const isSignedIn = sessionID !== kNotSignedIn
  const signedInUser =
    useResource("users", (users) => users.byID.get(sessionID)) ?? null
  const value = new Value(
    session !== undefined,
    sessionID,
    isSignedIn,
    signedInUser,
  )

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  )
}

export const useSessionInfo = () => useContext(SessionContext)
export const useSessionID = () => useContext(SessionContext).sessionID
export const useSignedInUser = () => useContext(SessionContext).signedInUser

export default SetSession
