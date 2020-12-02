/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the
); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an
 BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import { immerable } from "immer"

import { primaryMap } from "../reducers/resource"

type UserSSHKeyData = {
  id: number
  user: number
  type: string
  key: string
  comment: string
  bits: number
  fingerprint: string
}

type UserSSHKeyProps = UserSSHKeyData

class UserSSHKey {
  [immerable] = true

  constructor(
    readonly id: number,
    readonly user: number,
    readonly type: string,
    readonly key: string,
    readonly comment: string,
    readonly bits: number,
    readonly fingerprint: string,
  ) {}

  static new(props: UserSSHKeyProps) {
    return new UserSSHKey(
      props.id,
      props.user,
      props.type,
      props.key,
      props.comment,
      props.bits,
      props.fingerprint,
    )
  }

  static reducer = primaryMap<UserSSHKey, number>("usersshkeys")

  get props(): UserSSHKeyProps {
    return this
  }
}

export default UserSSHKey
