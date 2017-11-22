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

import { DATA_UPDATE } from "../actions/data"
import { EXTENSION_INSTALLATIONS_LOADED } from "../actions/extension"

const defaultState = {
  loadedForUserID: null,
}

const extensioninstallation = (state = defaultState, action) => {
  switch (action.type) {
    case EXTENSION_INSTALLATIONS_LOADED:
      return state.set("loadedForUserID", action.userID)

    case DATA_UPDATE:
      if (
        (action.updated && action.updated.has("sessions")) ||
        (action.deleted && action.deleted.has("sessions"))
      ) {
        return state
          .set("loadedForUserID", null)
          .set("byID", new Immutable.Map())
      }
      break

    default:
      break
  }
  return state
}

export default extensioninstallation
