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

import { primaryMap } from "../reducers/resource"

type UserEmailData = {
  id: number
  user: number
  address: string
  status: "trusted" | "verified" | "unverified"
  is_selected: boolean
}

type UserEmailProps = UserEmailData

class UserEmail {
  constructor(
    readonly id: number,
    readonly user: number,
    readonly address: string,
    readonly status: "trusted" | "verified" | "unverified",
    readonly isSelected: boolean
  ) {}

  static new(props: UserEmailProps) {
    return new UserEmail(
      props.id,
      props.user,
      props.address,
      props.status,
      props.is_selected
    )
  }

  static reducer = primaryMap<UserEmail, number>("useremails")

  get props(): UserEmailProps {
    return { ...this, is_selected: this.isSelected }
  }
}

export default UserEmail
