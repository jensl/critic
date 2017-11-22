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

import { fetchJSON } from "../utils/Fetch"
import {
  createResource,
  ErrorResponseJSON,
  expectStatuses,
  fetch,
  handleJSONResponse,
  include,
} from "../resources"
import { dataUpdate } from "./data"
import {
  LOGIN_REQUEST,
  Action,
  LOGIN_SUCCESS,
  LOGIN_FAILURE,
  LoginError,
} from "."
import { Dispatch } from "../state"

export const loginRequest = (): Action => ({
  type: LOGIN_REQUEST,
})

export const LOGIN_WAITING = "LOGIN_WAITING"
export const loginWaiting = () => ({
  type: LOGIN_WAITING,
})

export const loginSuccess = (): Action => ({
  type: LOGIN_SUCCESS,
})

export const loginFailure = (error: LoginError): Action => ({
  type: LOGIN_FAILURE,
  error,
})

export const LOGOUT_SUCCESS = "LOGOUT_SUCCESS"
export const logoutSuccess = () => ({
  type: LOGOUT_SUCCESS,
})

export const LOGOUT_FAILURE = "LOGOUT_FAILURE"
export const logoutFailure = (error: LoginError) => ({
  type: LOGOUT_FAILURE,
  error,
})

export type FieldValues = { [key: string]: string }

export const login = (data: FieldValues) => async (dispatch: Dispatch) => {
  dispatch(loginRequest())

  const { status, json } = await dispatch(
    createResource(
      "sessions",
      data,
      include("users"),
      expectStatuses(200, 403),
    ),
  )

  const { status, json } = dispatch(
    handleJSONResponse({
      ...(await dispatch(
        fetchJSON({
          path: "sessions",
          include: ["users"],
          post: data,
          expectStatus: [200, 403],
        }),
      )),
      resourceName: "sessions",
    }),
  )

  if (status !== 200) {
    dispatch(loginFailure((json as ErrorResponseJSON).error))
    return false
  }

  dispatch(loginSuccess())
  return true
}

export const logout = () => async (dispatch: Dispatch) => {
  await dispatch(
    fetchJSON({
      path: "sessions/current",
      options: { method: "DELETE" },
    }),
  )
  dispatch(loadSession())
}

export const resetSession = () =>
  dataUpdate({
    updates: new Map(),
    deleted: new Map([["sessions", new Set(["current"])]]),
    invalid: null,
  })

export const loadSession = () => fetch("sessions", "current")
