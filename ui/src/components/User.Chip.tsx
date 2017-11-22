import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Chip from "@material-ui/core/Chip"
import Avatar from "@material-ui/core/Avatar"
import AccountCircleIcon from "@material-ui/icons/AccountCircle"

import Registry from "."
import { UserID } from "../resources/types"
import { useResource } from "../utils"

const useStyles = makeStyles({
  userChip: { marginTop: 2, marginBottom: 2 },
  icon: {
    width: "100%",
    height: "100%",
  },
})

type Props = {
  className?: string
  userID: UserID
}

const UserChip: FunctionComponent<Props> = ({ className, userID }) => {
  const classes = useStyles()
  const users = useResource("users")
  const user = users.byID.get(userID)
  if (!user) return null
  return (
    <Chip
      className={clsx(className, classes.userChip)}
      component="span"
      avatar={
        <Avatar className={className}>
          <AccountCircleIcon className={classes.icon} />
        </Avatar>
      }
      label={user.fullname}
    />
  )
}

export default Registry.add("User.Chip", UserChip)
