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

import { createSelector } from "reselect"

const getAssignedUsers = (state, props) => props.review.assigned_reviewers
const getAddedUsers = (state) => state.data.userAssignment.addedUsers
const getRemovedUsers = (state) => state.data.userAssignment.removedUsers
const getUsers = (state) => state.data.user
const getPartialName = (state) => state.ui.rest.addUsername

export const getLocalUserAssignments = createSelector(
  [getAssignedUsers, getAddedUsers, getRemovedUsers, getUsers],
  (assignedUsers, addedUsers, removedUsers, users) => {
    var result = assignedUsers
    if (addedUsers && removedUsers) {
      const assignedAndAdded = new Set([...assignedUsers, ...addedUsers])
      result = new Set(
        [...assignedAndAdded].filter((user) => !removedUsers.has(user))
      )
    }
    return Array.from(result).map((uid) => users[uid])
  }
)

export const getUsersAsArray = createSelector([getUsers], (userObject) => {
  return Object.keys(userObject).map((key) => userObject[key])
})

export const getAutocompleteUsers = createSelector(
  [getPartialName, getUsersAsArray],
  (partialName, users) => {
    const matchingUsers = users.filter((user) =>
      user.name.includes(partialName)
    )
    if (matchingUsers.length < 10) {
      return matchingUsers
    } else {
      return []
    }
  }
)
