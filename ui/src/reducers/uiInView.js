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

import { SET_IN_VIEW } from "../actions/uiInView"

export const inView = (state = new Set(), action) => {
  switch (action.type) {
    case SET_IN_VIEW:
      if (!action.value === state.has(action.itemID)) {
        const newState = new Set(state)
        if (action.value) {
          newState.add(action.itemID)
        } else {
          newState.delete(action.itemID)
        }
        return newState
      }
      return state

    default:
      return state
  }
}
