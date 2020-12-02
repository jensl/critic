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

import Token from "../utils/Token"
import { Dispatch } from "../state"
import {
  Action,
  Toast,
  ADD_TOAST,
  SET_TOAST_STATE,
  TOAST_REMOVED,
  ToastState,
} from "."

export const addToast = (toast: Toast): Action => ({
  type: ADD_TOAST,
  toast,
})

const setToastState = (token: Token, state: ToastState): Action => ({
  type: SET_TOAST_STATE,
  token,
  state,
})

// const showedToast = (token: Token) => (
//   dispatch: Dispatch,
//   getState: GetState
// ) => {
//   for (const toast of getState().ui.rest.toasts) {
//     if (toast.token !== token) continue
//     dispatch(setToastState(token, null))
//     if (toast.timeoutMS !== null) {
//       setTimeout(() => dispatch(hideToast(token)), toast.timeoutMS)
//     }
//   }
// }

export const hideToast = (token: Token) => setToastState(token, "hiding")
export const removeToast = (token: Token) => setToastState(token, "removing")

export const toastRemoved = (token: Token): Action => ({
  type: TOAST_REMOVED,
  token,
})

interface ShowToastParams {
  type?: string
  title: string
  content?: string | JSX.Element
  timeoutMS?: number
}

export const showToast = ({
  type = "information",
  title,
  content,
  timeoutMS = 3000,
}: ShowToastParams) => (dispatch: Dispatch) => {
  const token = Token.create()
  dispatch(addToast(Toast.new({ token, type, title, content, timeoutMS })))
  return token
}
