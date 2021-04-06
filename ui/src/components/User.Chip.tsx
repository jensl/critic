import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Chip, { ChipProps } from "@material-ui/core/Chip"
import Avatar from "@material-ui/core/Avatar"
import AccountCircleIcon from "@material-ui/icons/AccountCircle"

import Registry from "."
import { UserID } from "../resources/types"
import { useResource, useSignedInUser } from "../utils"

const useStyles = makeStyles({
  userChip: { marginTop: 2, marginBottom: 2 },
  icon: {
    width: "100%",
    height: "100%",
  },
})

export type Props = {
  className?: string
  userID: UserID
  ChipProps?: Omit<ChipProps, "avatar" | "component" | "label">
}

const UserChip: FunctionComponent<Props> = ({
  className,
  userID,
  ChipProps,
}) => {
  const classes = useStyles()
  const signedInUser = useSignedInUser()
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
      color={userID === signedInUser?.id ? "secondary" : undefined}
      {...ChipProps}
    />
  )
}

export default Registry.add("User.Chip", UserChip)
