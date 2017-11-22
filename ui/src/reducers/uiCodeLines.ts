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

import {
  DOCUMENT_CLICKED,
  SET_SELECTION_SCOPE,
  SET_SELECTED_ELEMENTS,
  Action,
} from "../actions"

const defaultState = {
  showCreateCommentPopUp: false,
}

export const codeLines = (state = defaultState, action: Action) => {
  switch (action.type) {
    case SET_SELECTION_SCOPE:
      return { showCreateCommentPopUp: false }

    case SET_SELECTED_ELEMENTS:
      if (!action.isPending)
        return { showCreateCommentPopUp: action.selectedIDs.size !== 0 }
      return state

    case DOCUMENT_CLICKED:
      return { showCreateCommentPopUp: false }

    default:
      return state
  }
}
