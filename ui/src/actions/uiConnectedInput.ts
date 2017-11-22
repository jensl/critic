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

import { assertNotNull } from "../debug"
import Token from "../utils/Token"
import { CommentID, ReplyID } from "../resources/types"
import {
  REGISTER_CONNECTED_INPUT,
  SaveActionCreator,
  ConnectedInputUpdates,
  UPDATE_CONNECTED_INPUT,
  UNREGISTER_CONNECTED_INPUT,
  UpdateConnectedInputAction,
  UnregisterConnectedInputAction,
  Action,
} from "."
import { Dispatch, GetState } from "../state"
import { ConnectedInput } from "../reducers/uiConnectedInput"

export const getInputID = ({
  commentID = null,
  replyID = null,
}: {
  commentID: CommentID | null
  replyID: ReplyID | null
}) => {
  if (commentID !== null) return `comment_${commentID}`
  else if (replyID !== null) return `reply_${replyID}`
  return null
}

export const register = (
  saveActionCreator: SaveActionCreator,
  resourceValue: string
) => (dispatch: Dispatch) => {
  const inputID = Token.create()
  dispatch({
    type: REGISTER_CONNECTED_INPUT,
    inputID,
    saveActionCreator,
    resourceValue,
    controlValue: resourceValue,
  })
  return inputID
}

export const update = (
  inputID: Token,
  updates: ConnectedInputUpdates
): Action => ({
  type: UPDATE_CONNECTED_INPUT,
  inputID,
  updates,
})

export const unregister = (inputID: Token): Action => ({
  type: UNREGISTER_CONNECTED_INPUT,
  inputID,
})

const doSave = async (
  dispatch: Dispatch,
  connectedInput: ConnectedInput,
  controlValue: string,
  wasDismissed: boolean
) => {
  if (
    (controlValue || !wasDismissed) &&
    controlValue === connectedInput.resourceValue
  )
    return
  try {
    dispatch(
      update(connectedInput.inputID, {
        saveInProgress: true,
      })
    )
    await dispatch(connectedInput.saveActionCreator(controlValue, wasDismissed))
    dispatch(
      update(connectedInput.inputID, {
        resourceValue: controlValue,
        saveInProgress: false,
        saveFailed: false,
      })
    )
  } catch {
    dispatch(
      update(connectedInput.inputID, {
        saveInProgress: false,
        saveFailed: true,
      })
    )
  }
}

export const scheduleSave = (inputID: Token, controlValue: string) => (
  dispatch: Dispatch,
  getState: GetState
) => {
  const getConnectedInput = (inputID: Token) =>
    getState().ui.connectedInputs.get(inputID, null)

  const saveLater = async () => {
    const connectedInput = getConnectedInput(inputID)
    if (connectedInput === null) return
    dispatch(update(inputID, { timeoutID: null, saveInProgress: true }))
    doSave(dispatch, connectedInput, connectedInput.controlValue || "", false)
  }

  const connectedInput = getConnectedInput(inputID)
  assertNotNull(connectedInput)
  if (connectedInput === null) return

  // Schedule a save one second from now. If we've already scheduled one,
  // postpone it.
  if (connectedInput.timeoutID !== null) clearTimeout(connectedInput.timeoutID)
  const timeoutID = window.setTimeout(saveLater, 1000)
  dispatch(update(inputID, { timeoutID, controlValue }))
}

export const dismiss = (inputID: Token, controlValue: string) => async (
  dispatch: Dispatch,
  getState: GetState
) => {
  const connectedInput = getState().ui.connectedInputs.get(inputID, null)
  assertNotNull(connectedInput)
  if (connectedInput === null) return

  if (connectedInput.timeoutID !== null) clearTimeout(connectedInput.timeoutID)
  await doSave(dispatch, connectedInput, controlValue, true)
  dispatch(unregister(inputID))
}

export const focus = (inputID: Token) => (dispatch: Dispatch) => {
  const control = document.getElementById(`connected_input_${inputID}`)
  if (control) control.focus()
}
