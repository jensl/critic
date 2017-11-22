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

import { BRANCH_COMMITS_UPDATE } from "../actions"
import { COMMIT_REFS_UPDATE } from "../actions"

const defaultState = {
  byRef: new Immutable.Map(),
  byBranch: new Immutable.Map(),
  afterRebase: new Immutable.Map(),
}

const ByBranch = new Immutable.Record(
  {
    offset: null,
    count: null,
    commitIDs: new Immutable.List(),
  },
  "Commits.ByBranch"
)

const commitReducer = (state = defaultState, action) => {
  switch (action.type) {
    case COMMIT_REFS_UPDATE:
      return state.mergeIn(["byRef"], action.refs)

    case BRANCH_COMMITS_UPDATE:
      if (action.branchID !== null) {
        return state.setIn(["byBranch", action.branchID], new ByBranch(action))
      }
      if (action.beforeRebaseID !== null) {
        return state.setIn(
          ["afterRebase", action.afterRebaseID],
          action.commitIDs
        )
      }
      return state

    default:
      return state
  }
}

export default commitReducer
