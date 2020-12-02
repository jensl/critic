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
  fetch,
  createResource,
  deleteResource,
  updateResource,
  withArgument,
  withContext,
  withParameters,
} from "../resources"
import { UserID, UserEmailID, UserSSHKeyID } from "../resources/types"
import User from "../resources/user"
import { AsyncThunk } from "../state"

export const loadUsers = () => fetch("users")

export const loadUserEmails = (userID: UserID) =>
  fetch("useremails", withContext("users", userID))

export const loadUserSSHKeys = (userID: UserID) =>
  fetch("usersshkeys", withContext("users", userID))

export const setFullname = (userID: UserID, fullname: string) =>
  updateResource("users", { fullname }, withArgument(userID))

type SetPasswordPayload = {
  current?: string
  new: string
}

export const setPassword = (
  userID: UserID,
  currentPassword: string | null,
  newPassword: string,
): AsyncThunk<User> => async (dispatch) => {
  const password: SetPasswordPayload = { new: newPassword }
  if (currentPassword !== null) password.current = currentPassword
  return await dispatch(
    updateResource("users", { password }, withArgument(userID)),
  )
}

export const addEmailAddress = (userID: UserID, address: string) =>
  createResource("useremails", { address }, withContext("users", userID))

export const deleteEmailAddress = (userEmailID: UserEmailID) =>
  deleteResource("useremails", withArgument(userEmailID))

export const addSSHKey = (
  userID: UserID,
  type: string,
  key: string,
  comment: string,
) =>
  createResource(
    "usersshkeys",
    { type, key, comment },
    withContext("users", userID),
  )

export const deleteSSHKey = (keyID: UserSSHKeyID) =>
  deleteResource("usersshkeys", withArgument(keyID))
