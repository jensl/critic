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

import { DOCUMENT_CLICKED } from "../actions/ui"
import { SET_SELECTED_ELEMENTS } from "../actions"

import { SET_SHOW_ALL } from "../actions/uiCommitList"

const defaultState = {
  showActions: false,
  showActionsHint: false,
  showAll: false,
}

export const commitList = (state = defaultState, action) => {
  switch (action.type) {
    case DOCUMENT_CLICKED:
      return { ...state, showActions: false }

    case SET_SELECTED_ELEMENTS:
      const { isPending, scopeID, selectedIDs } = action
      if (!isPending && scopeID && scopeID.startsWith("commits:")) {
        const updates = {
          showActions: selectedIDs.size !== 0,
          showActionsHint: selectedIDs.size === 1,
        }
        return Object.assign({}, state, updates)
      }
      return state

    case SET_SHOW_ALL:
      return Object.assign({}, state, {
        showAll: action.value,
      })

    default:
      return state
  }
}
