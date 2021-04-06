/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
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

import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Chip, { Props as UserChipProps } from "./User.Chip"
import { UserID } from "../resources/types"
import User from "../resources/user"
import { compareByProps } from "../utils/Functions"
import { useResource } from "../utils"

const useStyles = makeStyles((theme) => ({
  chip: {
    "&:not(:first-child)": { marginLeft: theme.spacing(1) },
  },
}))

type Props = {
  className?: string
  userIDs: Iterable<UserID>
  UserChipProps?: Omit<UserChipProps, "userID">
}

const UserChips: FunctionComponent<Props> = ({
  className,
  userIDs,
  UserChipProps,
}) => {
  const classes = useStyles()
  const users = useResource("users")
  const allUsers = new Set<User>()
  for (const userID of userIDs) {
    const user = users.byID.get(userID)
    if (user) allUsers.add(user)
  }
  const sortedUsers = [...allUsers].sort(compareByProps("fullname", "name"))
  return (
    <span className={className}>
      {sortedUsers.map((user) => (
        <Chip
          className={classes.chip}
          key={user.id}
          userID={user.id}
          {...UserChipProps}
        />
      ))}
    </span>
  )
}

export default Registry.add("User.Chips", UserChips)
