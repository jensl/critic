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

import { combineReducers } from "redux"

import { primaryMap, lookupMap } from "../reducers/resource"
import { UserEmailID, UserID } from "./types"

export type UserStatus = "current" | "absent" | "retired" | "disabled"
export type PasswordStatus = "set" | "not-set" | "disabled"

type UserData = {
  id: UserID
  name: string
  fullname: string
  status: UserStatus
  email: UserEmailID | null
  password_status: PasswordStatus
  roles: string[]
}

type UserProps = {
  id: UserID
  name: string
  fullname: string
  status: UserStatus
  email: UserEmailID | null
  password_status: PasswordStatus
  roles: ReadonlySet<string>
}

class User {
  constructor(
    readonly id: UserID,
    readonly name: string,
    readonly fullname: string,
    readonly status: UserStatus,
    readonly email: number | null,
    readonly passwordStatus: PasswordStatus,
    readonly roles: ReadonlySet<string>
  ) {}

  static new(props: UserProps) {
    return new User(
      props.id,
      props.name,
      props.fullname,
      props.status,
      props.email,
      props.password_status,
      props.roles
    )
  }

  static prepare(value: UserData): UserProps {
    return { ...value, roles: new Set(value.roles || []) }
  }

  static reducer = combineReducers({
    byID: primaryMap<User, UserID>("users"),
    byName: lookupMap<User, string, UserID>("users", (user) => user.name),
  })

  get props(): UserProps {
    return { ...this, password_status: this.passwordStatus }
  }
}

export default User
