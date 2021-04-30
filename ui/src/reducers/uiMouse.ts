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

import { immerable } from "immer"

import produce from "./immer"

import { SET_MOUSE_IS_DOWN, SET_MOUSE_POSITION, Action } from "../actions"

class UIMouseState {
  [immerable] = true

  constructor(
    readonly isDown: boolean,
    readonly absoluteX: number,
    readonly absoluteY: number,
    readonly downAbsoluteX: number,
    readonly downAbsoluteY: number,
  ) {}

  static default() {
    return new UIMouseState(false, 0, 0, 0, 0)
  }
}

const reducer = produce<UIMouseState>((draft, action) => {
  switch (action.type) {
    case SET_MOUSE_IS_DOWN:
      if (action.value)
        Object.assign({
          isDown: true,
          downAbsoluteX: draft.absoluteX,
          downAbsoluteY: draft.absoluteY,
        })
      else draft.isDown = false
      break

    case SET_MOUSE_POSITION:
      Object.assign(draft, { absoluteX: action.x, absoluteY: action.y })
      break
  }
}, UIMouseState.default())

export default reducer
