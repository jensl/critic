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

import Resource from "../resources"
import { UserID, UserEmailID, UserSSHKeyID } from "../resources/types"
import { Dispatch } from "../state"

export const loadUsers = () => Resource.fetch("users")

export const loadUserEmails = (userID: UserID) =>
  Resource.fetch("useremails", { user: userID })

export const loadUserSSHKeys = (userID: UserID) =>
  Resource.fetch("usersshkeys", { user: userID })

export const setFullname = (userID: UserID, fullname: string) =>
  Resource.update("users", userID, { fullname })

type SetPasswordPayload = {
  current?: string
  new: string
}

export const setPassword = (
  userID: UserID,
  currentPassword: string,
  newPassword: string
) => (dispatch: Dispatch) => {
  const password: SetPasswordPayload = { new: newPassword }
  if (currentPassword !== null) password.current = currentPassword
  return dispatch(Resource.update("users", userID, { password }))
}

export const addEmailAddress = (userID: UserID, address: string) =>
  Resource.create("useremails", { user: userID, address })

export const deleteEmailAddress = (userEmailID: UserEmailID) =>
  Resource.delete("useremails", userEmailID)

export const addSSHKey = (
  userID: UserID,
  type: string,
  key: string,
  comment: string
) => Resource.create("usersshkeys", { user: userID, type, key, comment })

export const deleteSSHKey = (keyID: UserSSHKeyID) =>
  Resource.delete("usersshkeys", keyID)
