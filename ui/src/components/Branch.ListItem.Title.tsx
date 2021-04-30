import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Branch from "../resources/branch"

const useStyles = makeStyles({
  branchListItemTitle: {},
})

type OwnProps = {
  className?: string
  branch: Branch
}

const BranchListItemTitle: FunctionComponent<OwnProps> = ({
  className,
  branch,
}) => {
  const classes = useStyles()
  return (
    <Typography
      className={clsx(className, classes.branchListItemTitle)}
      variant="body1"
    >
      {branch.name}
    </Typography>
  )
}

export default Registry.add("Branch.ListItem.Title", BranchListItemTitle)
