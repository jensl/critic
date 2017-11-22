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

import { Action, LoginError } from "../actions"

type State = {
  signInPending: boolean
  signInSuccessful: boolean
  signInError: LoginError | null
}

const defaultState = {
  signInPending: false,
  signInSuccessful: false,
  signInError: null,
}

const session = (state: State = defaultState, action: Action): State => {
  switch (action.type) {
    case "LOGIN_REQUEST":
      return { ...defaultState, signInPending: true }

    case "LOGIN_SUCCESS":
      return { ...defaultState, signInSuccessful: true }

    case "LOGIN_FAILURE":
      return { ...defaultState, signInError: action.error }

    default:
      return state
  }
}

export default session
