import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"
import Avatar from "@material-ui/core/Avatar"
import AccountCircleIcon from "@material-ui/icons/AccountCircle"

import Registry from "."
import { useResource } from "../utils"

const useStyles = makeStyles((theme) => ({
  icon: {
    width: "100%",
    height: "100%",
  },
}))

type Props = {
  className?: string
  userID: number
}

const UserAvatar: FunctionComponent<Props> = ({ className, userID }) => {
  const classes = useStyles()
  const user = useResource("users", (users) => users.byID.get(userID))
  if (!user) return null
  return (
    <Avatar className={className}>
      <AccountCircleIcon className={classes.icon} />
    </Avatar>
  )
}

export default Registry.add("User.Avatar", UserAvatar)
