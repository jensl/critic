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

import { INSTALLED_EXTENSION_UPDATE } from "../actions/extension"
import { assignNewData } from "./index"

const defaultState = { installed: {} }

const extension = (state = Object.assign({}, defaultState), action) => {
  var newState
  switch (action.type) {
    case INSTALLED_EXTENSION_UPDATE:
      return Object.assign({}, state, assignNewData(action.extensions))

    default:
      return state
  }
}

export default extension
