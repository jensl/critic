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

import { Map } from "immutable"

import { UNPUBLISHED_CHANGES_PUBLISHED } from "../actions/batch"
import { LOGOUT_SUCCESS } from "../actions/session"

const batch = (state, action) => {
  switch (action.type) {
    case UNPUBLISHED_CHANGES_PUBLISHED:
      return state.deleteIn(["unpublished", action.reviewID])

    case LOGOUT_SUCCESS:
      return state.set("unpublished", new Map())

    default:
      return state
  }
}

export default batch
