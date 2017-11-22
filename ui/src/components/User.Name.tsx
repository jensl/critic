import React, { FunctionComponent } from "react"

import Registry from "."
import { UserID } from "../resources/types"
import { useResource } from "../utils"

type Props = {
  className?: string
  userID: UserID
}

const UserName: FunctionComponent<Props> = ({ className, userID }) => {
  const users = useResource("users")
  const user = users.byID.get(userID)
  if (!user) return null
  return <span className={className}>{user.fullname}</span>
}

export default Registry.add("User.Name", UserName)
