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

import { SET_MOUSE_IS_DOWN, SET_MOUSE_POSITION, Action } from "../actions"

type Props = {
  isDown: boolean
  absoluteX: number
  absoluteY: number
  downAbsoluteX: number
  downAbsoluteY: number
}

class UIMouseState extends Immutable.Record<Props>({
  isDown: false,
  absoluteX: 0,
  absoluteY: 0,
  downAbsoluteX: 0,
  downAbsoluteY: 0,
}) {}

const reducer = (state = new UIMouseState(), action: Action) => {
  switch (action.type) {
    case SET_MOUSE_IS_DOWN:
      return action.value
        ? state.merge({
            isDown: true,
            downAbsoluteX: state.absoluteX,
            downAbsoluteY: state.absoluteY,
          })
        : state.set("isDown", false)

    case SET_MOUSE_POSITION:
      return state.merge({ absoluteX: action.x, absoluteY: action.y })

    default:
      return state
  }
}

export default reducer
