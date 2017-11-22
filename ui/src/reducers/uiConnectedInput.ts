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

import Immutable from "immutable"

import { assertTrue, assertFalse, assertNotReached } from "../debug"
import {
  SaveActionCreator,
  REGISTER_CONNECTED_INPUT,
  UNREGISTER_CONNECTED_INPUT,
  Action,
  UPDATE_CONNECTED_INPUT,
} from "../actions"
import Token from "../utils/Token"

type Props = {
  // Initial / static state.
  inputID: Token
  saveActionCreator: SaveActionCreator

  // Dynamic state.
  resourceValue: string | null
  controlValue: string | null
  timeoutID: number | null
  saveInProgress: boolean
  saveFailed: boolean
}

export class ConnectedInput extends Immutable.Record<Props>({
  // Initial / static state.
  inputID: Token.invalid,
  saveActionCreator: assertNotReached,

  // Dynamic state.
  resourceValue: null,
  controlValue: null,
  timeoutID: null,
  saveInProgress: false,
  saveFailed: false,
}) {}

export type ConnectedInputs = Immutable.Map<Token, ConnectedInput>

export const connectedInputs = (
  state = Immutable.Map<Token, ConnectedInput>(),
  action: Action
) => {
  switch (action.type) {
    case REGISTER_CONNECTED_INPUT:
      assertFalse(state.has(action.inputID))
      return state.set(action.inputID, new ConnectedInput(action))

    case UPDATE_CONNECTED_INPUT:
      assertTrue(state.has(action.inputID))
      return state.mergeIn([action.inputID], action.updates)

    case UNREGISTER_CONNECTED_INPUT:
      assertTrue(state.has(action.inputID))
      return state.delete(action.inputID)

    default:
      return state
  }
}
