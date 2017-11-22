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
  ASSIGN_USER,
  UNASSIGN_USER,
  RESET_ASSIGNMENTS,
} from "../actions/userAssignment"

const defaultState = { addedUsers: new Set(), removedUsers: new Set() }

const userAssignment = (state = Object.assign({}, defaultState), action) => {
  var newState
  var newAddedUsers
  var newRemovedUsers
  switch (action.type) {
    case ASSIGN_USER:
      newState = Object.assign({}, state)
      newAddedUsers = new Set(state.addedUsers)
      newRemovedUsers = new Set(state.removedUsers)

      const hadRemovedUser = newRemovedUsers.delete(action.user)

      if (!hadRemovedUser) {
        newAddedUsers.add(action.user)
      }
      newState.addedUsers = newAddedUsers
      newState.removedUsers = newRemovedUsers
      return newState

    case UNASSIGN_USER:
      newState = Object.assign({}, state)
      newAddedUsers = new Set(state.addedUsers)
      newRemovedUsers = new Set(state.removedUsers)

      const hadAddedUser = newAddedUsers.delete(action.user)

      if (!hadAddedUser) {
        newRemovedUsers.add(action.user)
      }
      newState.removedUsers = newRemovedUsers
      newState.addedUsers = newAddedUsers
      return newState

    case RESET_ASSIGNMENTS:
      return Object.assign({}, defaultState)

    default:
      return state
  }
}

export default userAssignment
