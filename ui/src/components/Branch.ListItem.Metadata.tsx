import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import UserListItem from "./User.ListItem"
import Branch from "../resources/branch"
import { map, useResource } from "../utils"

const useStyles = makeStyles({
  branchListItemMetadata: {
    opacity: 0.5,
  },
})

type OwnProps = {
  className?: string
  branch: Branch
}

const BranchListItemMetadata: FunctionComponent<OwnProps> = ({
  className,
  branch,
}) => {
  const classes = useStyles()
  const head = useResource("commits", ({ byID }) => byID.get(branch.head))
  return (
    <div>
      <Typography
        className={clsx(className, classes.branchListItemMetadata)}
        display="inline"
        component="span"
      >
        {head?.sha1.substring(0, 8)}
      </Typography>
    </div>
  )
}

export default Registry.add("Branch.ListItem.Metadata", BranchListItemMetadata)
