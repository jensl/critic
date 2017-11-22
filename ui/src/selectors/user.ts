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

import { makeMap, groupBy } from "../utils"
import { State } from "../state"
import User from "../resources/user"
import { UserID } from "../resources/types"

type UserProp = { user: User | null }
type UserIDProp = { userID: UserID }
type GetUserProps = UserProp | UserIDProp

const isUserProp = (props: GetUserProps): props is UserProp => "user" in props

export const getUser = (state: State, props: GetUserProps) =>
  isUserProp(props) ? props.user : state.resource.users.byID.get(props.userID)

const getUserEmails = (state: State) => state.resource.useremails
const getRepositoryFilters = (state: State) => state.resource.repositoryfilters

export const getUserEmailsPerUser = createSelector(
  getUserEmails,
  (userEmails) => {
    return makeMap(
      groupBy(userEmails.values(), (userEmail) => userEmail.user),
      {
        mapValue: (userEmails) => new Set(userEmails),
      }
    )
  }
)

export const getRepositoryFiltersPerUser = createSelector(
  getRepositoryFilters,
  (repositoryFilters) => {
    return makeMap(
      groupBy(
        repositoryFilters.values(),
        (repositoryFilter) => repositoryFilter.subject
      ),
      {
        mapValue: (repositoryFilters) => new Set(repositoryFilters),
      }
    )
  }
)

export const getRepositoryFiltersForUser = createSelector(
  getRepositoryFiltersPerUser,
  getUser,
  (repositoryFiltersPerUser, user) =>
    user ? repositoryFiltersPerUser.get(user.id) || new Set() : null
)
